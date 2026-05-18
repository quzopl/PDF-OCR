from pathlib import Path

from docx import Document

from app.formats.docx import write_docx
from app.ocr.base import OcrPage, OcrResult, Word


def test_docx_contains_text(tmp_path: Path):
    result = OcrResult(
        pages=[
            OcrPage(1, 100, 100, [Word("Hello", (0, 0, 10, 5), 0.9)]),
            OcrPage(2, 100, 100, [Word("World", (0, 0, 10, 5), 0.9)]),
        ],
        engine="x",
        languages=["en"],
    )
    out = write_docx(result, tmp_path)
    doc = Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Hello" in text and "World" in text
