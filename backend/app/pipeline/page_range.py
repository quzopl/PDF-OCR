from __future__ import annotations

from pathlib import Path

import pypdf


def extract_page_range(src: Path, dst: Path, *, start: int, end: int) -> None:
    """Write a PDF containing pages [start, end] (1-indexed, inclusive)."""
    reader = pypdf.PdfReader(str(src))
    total = len(reader.pages)
    if start < 1 or end < start or end > total:
        raise ValueError(f"invalid page range [{start},{end}] for PDF with {total} pages")
    writer = pypdf.PdfWriter()
    for i in range(start - 1, end):
        writer.add_page(reader.pages[i])
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as f:
        writer.write(f)
