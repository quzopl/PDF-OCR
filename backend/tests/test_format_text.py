from pathlib import Path

from app.formats.text import write_txt
from app.ocr.base import OcrPage, OcrResult, Word


def _result() -> OcrResult:
    pages = [
        OcrPage(
            page_number=1,
            width=100,
            height=100,
            words=[
                Word("Hello", (0, 0, 10, 5), 0.9),
                Word("world", (12, 0, 22, 5), 0.9),
            ],
        ),
        OcrPage(
            page_number=2,
            width=100,
            height=100,
            words=[Word("Page2", (0, 0, 10, 5), 0.9)],
        ),
    ]
    return OcrResult(pages=pages, engine="x", languages=["en"])


def test_writes_text(tmp_path: Path):
    out = write_txt(_result(), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Hello world" in text
    assert "Page2" in text
    assert "\f" in text or "\n\n" in text  # page separator
