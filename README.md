# NCERT Books Downloader

<p align="center">
<img width="80" src="logo.jpg"/>
</p>

Download free NCERT textbooks as merged PDFs, organised by class and subject. NCERT (National Council of Educational Research and Training) publishes the official school textbooks used across India — this tool lets you download and save any of them offline as a single clean PDF, without navigating the NCERT website manually.

## What it does

- Lets you pick a class and subject interactively, or specify them via flags
- Downloads the official chapter files from NCERT's servers
- Merges them into a single PDF per book, saved to a `downloads/` folder
- Skips books already downloaded — safe to re-run at any time

---

## Quick start (recommended)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv run main.py
```

`uv` installs all dependencies automatically on first run. The script will guide you through picking a class, subject, and which books to download.

### Don't have uv?

If you already have Python 3.10+ installed:

```sh
pip install pypdf questionary requests rich
python main.py
```

---

## Interactive usage

When you run the script without any flags, it walks you through three steps:

1. **Pick a class** — choose from Class 1 to 14, or download all classes at once
2. **Pick a subject** — filtered to what's available for that class
3. **Pick books** — download everything, or select specific titles with the spacebar

Books are saved to `downloads/Class <N>/<Subject>/<Title>.pdf`.

---

## Non-interactive usage

Pass flags to skip the prompts entirely — useful for scripting or automation:

```sh
uv run main.py --class 10                        # all Class 10 books
uv run main.py --class 10 --subject Mathematics  # specific class + subject
uv run main.py --list                            # browse the full catalog without downloading
uv run main.py --download-only                   # download zip files, skip PDF merging
uv run main.py --merge-only                      # merge already-downloaded zips into PDFs
uv run main.py --keep-zips                       # keep zip files after merging
uv run main.py --out ./books                     # save to a custom directory
uv run main.py --concurrency 5                   # limit parallel downloads
```

Re-running is always safe — files already downloaded or merged are skipped automatically.

---

## Updating the book catalog

The list of available books is stored in `data.json`. Regenerate it if the NCERT catalog changes:

```sh
uv run generate_data.py
```

---

## Development

```sh
uv sync --group dev   # install dependencies including dev tools
uv run main.py        # run the script
```

### Running tests

```sh
uv run pytest tests/
```
