import json
from pathlib import Path

from app.formats.word_positions import write_word_positions_json
from app.ocr.base import OcrPage, OcrResult, Word


def test_json_structure(tmp_path: Path):
    result = OcrResult(
        pages=[
            OcrPage(1, 595.0, 842.0, [Word("Cześć", (10, 20, 50, 35), 0.87)]),
        ],
        engine="paddle",
        languages=["pl"],
    )
    out = write_word_positions_json(result, tmp_path)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["engine"] == "paddle"
    assert data["languages"] == ["pl"]
    assert len(data["pages"]) == 1
    page = data["pages"][0]
    assert page["page_number"] == 1
    assert page["width"] == 595.0
    assert page["words"][0]["text"] == "Cześć"
    assert page["words"][0]["bbox"] == [10.0, 20.0, 50.0, 35.0]
    assert page["words"][0]["confidence"] == 0.87
