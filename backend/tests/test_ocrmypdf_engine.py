from pathlib import Path

import pytest

from app.ocr.base import EngineOptions
from app.ocr.ocrmypdf_engine import OcrMyPdfEngine

pytestmark = pytest.mark.skipif(
    not __import__("shutil").which("tesseract"), reason="tesseract not installed"
)


def test_runs_on_text_pdf(tmp_path: Path, text_pdf: Path):
    progress_calls = []

    def progress(*, pages_done: int, active_workers: int) -> None:
        progress_calls.append((pages_done, active_workers))

    engine = OcrMyPdfEngine()
    opts = EngineOptions(
        languages=["eng"], workers=1, use_cuda=False, deskew=False, denoise=False
    )
    result = engine.run(text_pdf, opts, tmp_path, progress)

    assert len(result.pages) == 1
    assert result.raw_searchable_pdf is not None
    assert result.raw_searchable_pdf.exists()
    text = " ".join(w.text for w in result.pages[0].words).lower()
    assert "hello" in text
    assert progress_calls, "engine must report progress"
