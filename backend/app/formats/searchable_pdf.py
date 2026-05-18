from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

import pikepdf
from pdf2image import convert_from_path
from reportlab.pdfgen import canvas

from app.ocr.base import OcrResult


def write_searchable_pdf(
    result: OcrResult, out_dir: Path, *, original_pdf: Path
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "output.pdf"
    if result.raw_searchable_pdf is not None:
        shutil.copyfile(result.raw_searchable_pdf, out)
        return out
    _build_overlay(result, original_pdf, out)
    return out


def _build_overlay(result: OcrResult, original_pdf: Path, out: Path) -> None:
    # Render original pages to images, draw invisible text at the OCR boxes on top.
    images = convert_from_path(str(original_pdf), dpi=300)
    base_pdf = pikepdf.Pdf.open(str(original_pdf))
    overlay_buf = BytesIO()
    # Use the original page sizes (points) from base_pdf
    sizes = [
        (float(p.mediabox[2] - p.mediabox[0]), float(p.mediabox[3] - p.mediabox[1]))
        for p in base_pdf.pages
    ]

    c = canvas.Canvas(overlay_buf)
    for page_idx, page in enumerate(result.pages):
        if page_idx >= len(sizes):
            break
        page_w, page_h = sizes[page_idx]
        img = images[page_idx]
        sx = page_w / img.width
        sy = page_h / img.height
        c.setPageSize((page_w, page_h))
        # Invisible text (render mode 3)
        c.saveState()
        c.setFillColorRGB(0, 0, 0)
        text = c.beginText()
        for w in page.words:
            x0, y0, x1, y1 = w.bbox
            # Convert image-space box (top-left origin) to PDF space (bottom-left origin).
            pdf_x = x0 * sx
            pdf_y = page_h - (y1 * sy)
            font_size = max(1.0, (y1 - y0) * sy)
            c.setFont("Helvetica", font_size)
            text = c.beginText(pdf_x, pdf_y)
            text.setTextRenderMode(3)  # invisible
            text.textLine(w.text)
            c.drawText(text)
        c.restoreState()
        c.showPage()
    c.save()

    overlay_buf.seek(0)
    overlay = pikepdf.Pdf.open(overlay_buf)
    for base_page, overlay_page in zip(base_pdf.pages, overlay.pages):
        base_page.add_overlay(overlay_page)
    base_pdf.save(str(out))
