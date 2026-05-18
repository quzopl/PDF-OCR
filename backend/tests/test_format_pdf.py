from pathlib import Path

import pdfplumber

from app.formats.searchable_pdf import write_searchable_pdf
from app.ocr.base import OcrPage, OcrResult, Word


def test_passthrough_when_engine_provided(tmp_path: Path, text_pdf: Path):
    # Pretend OCRmyPDF gave us a searchable PDF already
    result = OcrResult(
        pages=[OcrPage(1, 595, 842, [])],
        engine="ocrmypdf",
        languages=["en"],
        raw_searchable_pdf=text_pdf,
    )
    out = write_searchable_pdf(result, tmp_path, original_pdf=text_pdf)
    assert out.exists()
    # Should be a copy/reference, not the original path
    assert out.parent == tmp_path


def test_overlay_for_paddle(tmp_path: Path, text_pdf: Path):
    result = OcrResult(
        pages=[OcrPage(1, 595.0, 842.0, [Word("Hello", (72.0, 800.0, 200.0, 820.0), 0.95)])],
        engine="paddle",
        languages=["en"],
        raw_searchable_pdf=None,
    )
    out = write_searchable_pdf(result, tmp_path, original_pdf=text_pdf)
    assert out.exists()
    with pdfplumber.open(str(out)) as pdf:
        extracted = pdf.pages[0].extract_text() or ""
    assert "Hello" in extracted
