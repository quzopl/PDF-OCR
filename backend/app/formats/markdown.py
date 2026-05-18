from __future__ import annotations

from pathlib import Path

from app.formats.text import _page_text
from app.ocr.base import OcrResult


def write_markdown(result: OcrResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "output.md"
    chunks: list[str] = []
    for i, page in enumerate(result.pages):
        if i > 0:
            chunks.append("\n---\n")
        chunks.append(f"## Page {page.page_number}\n\n{_page_text(page)}\n")
    out.write_text("\n".join(chunks), encoding="utf-8")
    return out
