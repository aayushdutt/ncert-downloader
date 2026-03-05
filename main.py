#!/usr/bin/env python3
"""NCERT Books Downloader — download and assemble NCERT textbooks as PDFs."""

import json
import shutil
import zipfile
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import questionary
import requests
from pypdf import PdfWriter
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, MofNCompleteColumn, TextColumn
from rich.table import Table

console = Console()

BASE_URL = "https://ncert.nic.in/textbook/pdf/"
DATA_FILE = Path(__file__).parent / "data.json"

# Consistent prompt style: cyan highlight, no reverse-video white overlay
STYLE = questionary.Style([
    ("highlighted", "fg:cyan bold noreverse"),
    ("selected", "fg:green bold"),
    ("pointer", "fg:cyan bold"),
    ("answer", "fg:cyan bold"),
    ("instruction", "fg:#666666"),
    ("checkbox", "fg:#666666"),
    ("checkbox-selected", "fg:green bold"),
])


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def iter_books(data, cls_filter=None, subj_filter=None):
    for cls, subjects in sorted(data.items(), key=lambda x: int(x[0])):
        if cls_filter and cls != str(cls_filter):
            continue
        for subject, books in subjects.items():
            if subj_filter and subject.lower() != subj_filter.lower():
                continue
            for book in books:
                if book.get("code"):
                    yield cls, subject, book


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------

def interactive_select(data):
    """Guided prompts: class → subject → all or pick specific books.
    Returns a list of (cls, subject, book) tuples, or None if cancelled."""

    classes = sorted(data.keys(), key=int)

    cls_answer = questionary.select(
        "Which class?",
        choices=["All classes"] + [f"Class {c}" for c in classes],
        style=STYLE,
    ).ask()
    if cls_answer is None:
        return None

    cls_filter = None if cls_answer == "All classes" else cls_answer.split()[1]

    subjects = sorted({
        subj
        for cls, subj_dict in data.items()
        if not cls_filter or cls == cls_filter
        for subj in subj_dict
    })

    subj_answer = questionary.select(
        "Which subject?",
        choices=["All subjects"] + subjects,
        style=STYLE,
    ).ask()
    if subj_answer is None:
        return None

    subj_filter = None if subj_answer == "All subjects" else subj_answer
    all_books = list(iter_books(data, cls_filter, subj_filter))
    if not all_books:
        return []

    n = len(all_books)
    # Show context when spanning multiple subjects/classes
    multi_subject = subj_filter is None
    def book_label(cls, subject, book):
        return f"{subject}  —  {book['text']}" if multi_subject else book["text"]

    mode = questionary.select(
        f"Found {n} book{'s' if n != 1 else ''}. What would you like to download?",
        choices=[
            questionary.Choice(f"All {n} books", value="all"),
            questionary.Choice("Let me pick specific ones", value="pick"),
        ],
        style=STYLE,
    ).ask()
    if mode is None:
        return None

    if mode == "all":
        return all_books

    # Checkbox: none pre-selected so user makes deliberate choices
    choices = [
        questionary.Choice(title=book_label(cls, subject, book), value=(cls, subject, book))
        for cls, subject, book in all_books
    ]
    selected = questionary.checkbox(
        "Select books:",
        choices=choices,
        instruction="  (arrows to navigate, space to check/uncheck, enter to confirm)",
        validate=lambda x: True if x else "Press space to select at least one book first",
        style=STYLE,
    ).ask()
    if selected is None:
        return None

    return selected


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def show_catalog(data, cls_filter=None, subj_filter=None):
    table = Table(title="NCERT Books Catalog", show_lines=True)
    table.add_column("Class", style="cyan", justify="center", no_wrap=True)
    table.add_column("Subject", style="green", no_wrap=True)
    table.add_column("Books", style="white")

    seen = set()
    for cls, subject, _ in iter_books(data, cls_filter, subj_filter):
        if (cls, subject) not in seen:
            titles = [b["text"] for b in data[cls][subject] if b.get("code")]
            table.add_row(f"Class {cls}", subject, "\n".join(titles))
            seen.add((cls, subject))

    console.print(table)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_book(cls, subject, book, out_dir):
    dest = out_dir / f"Class {cls}" / subject / f"{book['text']}.zip"
    if dest.exists():
        return "skipped"

    url = f"{BASE_URL}{book['code']}dd.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".zip.tmp")
    try:
        # Resume from a previous partial download if the tmp file exists
        resume_at = tmp.stat().st_size if tmp.exists() else 0
        headers = {"Range": f"bytes={resume_at}-"} if resume_at else {}

        r = requests.get(url, stream=True, timeout=30, headers=headers)
        r.raise_for_status()

        # Server may ignore the Range header (returns 200 instead of 206)
        if r.status_code == 200 and resume_at:
            resume_at = 0  # restart; don't append stale bytes

        with open(tmp, "ab" if resume_at else "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        tmp.rename(dest)
        return "ok"
    except Exception as e:
        return f"error: {e}"  # keep tmp for next resume attempt


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def merge_book(zip_path, keep_zip):
    out_pdf = zip_path.with_suffix(".pdf")
    if out_pdf.exists():
        return "skipped"

    temp_dir = zip_path.parent / f"_tmp_{zip_path.stem}"
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(temp_dir)

        # Sort alphabetically; NCERT names prelim/cover with a non-numeric
        # suffix (e.g. *ps.pdf) which sorts last — move it to the front.
        pdf_files = sorted(temp_dir.rglob("*.pdf"))
        if not pdf_files:
            return "error: no PDFs found in zip"
        if len(pdf_files) > 1:
            pdf_files.insert(0, pdf_files.pop())

        writer = PdfWriter()
        for pdf in pdf_files:
            writer.append(str(pdf))
        with open(out_pdf, "wb") as f:
            writer.write(f)

        if not keep_zip:
            zip_path.unlink()
        return "ok"
    except Exception as e:
        return f"error: {e}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

def run_concurrent(label, items, fn, concurrency):
    ok = skipped = errors = 0
    with Progress(
        SpinnerColumn(),
        TextColumn(f"  [bold]{label}[/bold]"),
        BarColumn(bar_width=40),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(label, total=len(items))
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(fn, *item): item for item in items}
            for future in as_completed(futures):
                result = future.result()
                if result == "ok":
                    ok += 1
                elif result == "skipped":
                    skipped += 1
                else:
                    errors += 1
                    console.log(f"[red]{result}[/red]")
                progress.advance(task)
    return ok, skipped, errors


def print_summary(ok, skipped, errors):
    parts = []
    if ok:
        parts.append(f"[green]{ok} done[/green]")
    if skipped:
        parts.append(f"[dim]{skipped} skipped[/dim]")
    if errors:
        parts.append(f"[red]{errors} failed[/red]")
    if parts:
        console.print("  " + ", ".join(parts))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Download NCERT textbooks as merged PDFs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  uv run main.py                        interactive mode (default)
  uv run main.py --class 10             all Class 10 books, no prompts
  uv run main.py --class 10 --subject Mathematics
  uv run main.py --list                 browse the full catalog
  uv run main.py --download-only        download zips, skip merging
  uv run main.py --merge-only           merge existing zips, skip downloading
  uv run main.py --keep-zips            keep zip files after merging
""",
    )
    parser.add_argument("--class", dest="cls", metavar="N", help="filter by class number")
    parser.add_argument("--subject", metavar="NAME", help="filter by subject name")
    parser.add_argument("--list", action="store_true", help="list available books and exit")
    parser.add_argument("--download-only", action="store_true", help="skip PDF merging")
    parser.add_argument("--merge-only", action="store_true", help="skip downloading")
    parser.add_argument("--keep-zips", action="store_true", help="keep zip files after merging")
    parser.add_argument("--out", default="downloads", metavar="DIR", help="output directory (default: downloads)")
    parser.add_argument("--concurrency", type=int, default=20, metavar="N", help="parallel downloads (default: 20)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    data = load_data()

    console.print("\n[bold cyan]NCERT Books Downloader[/bold cyan]\n")

    if args.list:
        show_catalog(data, args.cls, args.subject)
        return

    cls_filter = args.cls
    subj_filter = args.subject
    interactive = not cls_filter and not subj_filter and not args.merge_only

    if interactive:
        books = interactive_select(data)
        if books is None:
            return  # user cancelled (Ctrl+C)
        console.print()
    else:
        books = list(iter_books(data, cls_filter, subj_filter))

    if not books:
        console.print("[yellow]No books selected.[/yellow]")
        return

    n = len(books)

    if not args.merge_only:
        console.print(f"[bold]Downloading {n} book{'s' if n != 1 else ''}...[/bold]")
        items = [(cls, subject, book, out_dir) for cls, subject, book in books]
        ok, skipped, errors = run_concurrent("Downloading", items, download_book, args.concurrency)
        print_summary(ok, skipped, errors)

    if not args.download_only:
        zip_files = sorted(out_dir.rglob("*.zip"))
        if zip_files:
            console.print(f"\n[bold]Merging {len(zip_files)} book{'s' if len(zip_files) != 1 else ''}...[/bold]")
            items = [(z, args.keep_zips) for z in zip_files]
            ok, skipped, errors = run_concurrent("Merging", items, merge_book, concurrency=4)
            print_summary(ok, skipped, errors)

    console.print(f"\n[bold green]Done![/bold green] Books saved to [cyan]{out_dir.resolve()}[/cyan]\n")


if __name__ == "__main__":
    main()
