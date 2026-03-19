#!/usr/bin/env python3
"""Fetch the NCERT textbook page and regenerate data.json."""

import json
import re
from pathlib import Path

import requests

NCERT_URL = "https://ncert.nic.in/textbook.php"


def strip_js_comments(js_code):
    """Remove multi-line /* ... */ and single-line // comments from JavaScript."""
    # Remove multi-line comments (non-greedy)
    js_code = re.sub(r"/\*.*?\*/", "", js_code, flags=re.DOTALL)
    # Remove single-line comments (optional, but safe)
    js_code = re.sub(r"//.*$", "", js_code, flags=re.MULTILINE)
    return js_code


def fetch_script(url: str) -> str:
    """Download the NCERT page and return the JS block containing change1()."""
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    blocks = re.findall(
        r"<script[^>]*>(.*?)</script>", r.text, re.DOTALL | re.IGNORECASE
    )
    for block in blocks:
        if "tclass.value" in block:
            return block
    raise ValueError("Could not find book-data script block in the page")


def parse_script(script: str) -> dict:
    """Parse the change1() if-else chain into {class: {subject: [books]}}."""
    # Strip comments first to avoid parsing old data
    script = strip_js_comments(script)

    result = {}
    for condition in script.split("else if"):
        class_m = re.search(r"tclass\.value\s*==\s*(\d+)", condition)
        subj_m = re.search(
            r'tsubject\.options\[sind\]\.text\s*==\s*"([^"]+)"', condition
        )
        if not class_m or not subj_m:
            continue
        cls, subj = class_m.group(1), subj_m.group(1)
        if subj == "..Select Subject..":
            continue

        result.setdefault(cls, {}).setdefault(subj, [])

        book_pat = (
            r'tbook\.options\[(\d+)\]\.text\s*=\s*"([^"]+)";'
            r'[\s\S]*?tbook\.options\[\1\]\.value\s*=\s*"([^"]+)"'
        )
        for m_book in re.finditer(book_pat, condition):
            _, title, full_code = m_book.groups()
            if title in ("..Select Book Title..", "") or not title.strip():
                continue
            m = re.match(r"textbook\.php\?([a-zA-Z0-9]+)=(\d+-\d+)", full_code)
            result[cls][subj].append(
                {
                    "text": title,
                    "code": m.group(1) if m else "",
                    "chapters": m.group(2) if m else "",
                }
            )
    return result


def main():
    print(f"Fetching {NCERT_URL} …")
    data = parse_script(fetch_script(NCERT_URL))
    out = Path(__file__).parent / "data.json"
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    books = sum(len(b) for s in data.values() for b in s.values())
    print(f"Written {out}  ({len(data)} classes, {books} books)")


if __name__ == "__main__":
    main()
