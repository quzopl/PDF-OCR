from pathlib import Path

import pypdf

from app.pipeline.page_range import extract_page_range


def test_extract_subset(tmp_path: Path, multipage_pdf: Path):
    out = tmp_path / "out.pdf"
    extract_page_range(multipage_pdf, out, start=3, end=5)
    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) == 3


def test_extract_full(tmp_path: Path, multipage_pdf: Path):
    out = tmp_path / "out.pdf"
    extract_page_range(multipage_pdf, out, start=1, end=10)
    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) == 10


def test_extract_out_of_range(tmp_path: Path, multipage_pdf: Path):
    out = tmp_path / "out.pdf"
    import pytest

    with pytest.raises(ValueError):
        extract_page_range(multipage_pdf, out, start=1, end=99)
