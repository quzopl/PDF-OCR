from app.ocr.base import OcrPage, OcrResult, Word


def test_word_dataclass():
    w = Word(text="Cześć", bbox=(0.0, 0.0, 10.0, 5.0), confidence=0.97)
    assert w.text == "Cześć"
    assert w.bbox == (0.0, 0.0, 10.0, 5.0)


def test_ocr_result_iteration():
    page = OcrPage(page_number=1, width=595.0, height=842.0, words=[])
    result = OcrResult(pages=[page], engine="paddle", languages=["pl"])
    assert result.pages[0].page_number == 1
    assert result.raw_searchable_pdf is None
