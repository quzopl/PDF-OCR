from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _ensure_fixtures() -> None:
    FIXTURE_DIR.mkdir(exist_ok=True)
    multipage = FIXTURE_DIR / "multipage.pdf"
    if not multipage.exists():
        c = canvas.Canvas(str(multipage), pagesize=A4)
        for i in range(1, 11):
            c.setFont("Helvetica", 24)
            c.drawString(72, 800, f"Page {i}")
            c.drawString(72, 760, f"Marker-{i}")
            c.showPage()
        c.save()
    text = FIXTURE_DIR / "text_simple.pdf"
    if not text.exists():
        c = canvas.Canvas(str(text), pagesize=A4)
        c.setFont("Helvetica", 18)
        c.drawString(72, 800, "Hello world OCR test")
        c.showPage()
        c.save()


@pytest.fixture
def multipage_pdf() -> Path:
    return FIXTURE_DIR / "multipage.pdf"


@pytest.fixture
def text_pdf() -> Path:
    return FIXTURE_DIR / "text_simple.pdf"
