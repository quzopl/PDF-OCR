from pathlib import Path

from app.formats.markdown import write_markdown
from app.ocr.base import OcrPage, OcrResult, Word


def test_pages_separated_by_hr(tmp_path: Path):
    result = OcrResult(
        pages=[
            OcrPage(1, 100, 100, [Word("Alpha", (0, 0, 10, 5), 0.9)]),
            OcrPage(2, 100, 100, [Word("Beta", (0, 0, 10, 5), 0.9)]),
        ],
        engine="x",
        languages=["en"],
    )
    out = write_markdown(result, tmp_path)
    md = out.read_text(encoding="utf-8")
    assert "Alpha" in md and "Beta" in md
    assert "\n---\n" in md
    assert "## Page 1" in md and "## Page 2" in md
