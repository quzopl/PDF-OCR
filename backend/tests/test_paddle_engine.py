from pathlib import Path

import pytest

from app.ocr.base import EngineOptions
from app.ocr.paddle_engine import PaddleEngine

pytestmark = pytest.mark.skipif(
    not __import__("importlib.util").util.find_spec("paddleocr"),
    reason="paddleocr not installed",
)


def test_runs_on_text_pdf(tmp_path: Path, text_pdf: Path):
    calls: list[tuple[int, int]] = []

    def progress(*, pages_done: int, active_workers: int) -> None:
        calls.append((pages_done, active_workers))

    engine = PaddleEngine()
    opts = EngineOptions(
        languages=["en"], workers=1, use_cuda=False, deskew=False, denoise=False
    )
    result = engine.run(text_pdf, opts, tmp_path, progress)
    assert len(result.pages) == 1
    text = " ".join(w.text for w in result.pages[0].words).lower()
    assert "hello" in text
    assert any(p == 1 for p, _ in calls)
