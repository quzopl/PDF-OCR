from __future__ import annotations

from pathlib import Path

from app.ocr.base import OcrPage, OcrResult


def _page_text(page: OcrPage) -> str:
    # Group words into lines by y-mid proximity; words sorted by x.
    if not page.words:
        return ""
    sorted_words = sorted(page.words, key=lambda w: ((w.bbox[1] + w.bbox[3]) / 2, w.bbox[0]))
    line_tol = max(8.0, page.height * 0.012)
    lines: list[list] = [[sorted_words[0]]]
    for w in sorted_words[1:]:
        y_mid = (w.bbox[1] + w.bbox[3]) / 2
        prev_mid = (lines[-1][-1].bbox[1] + lines[-1][-1].bbox[3]) / 2
        if abs(y_mid - prev_mid) <= line_tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return "\n".join(" ".join(w.text for w in sorted(line, key=lambda x: x.bbox[0])) for line in lines)


def write_txt(result: OcrResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "output.txt"
    parts = [f"--- Page {page.page_number} ---\n{_page_text(page)}" for page in result.pages]
    out.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return out
