from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.formats.docx import write_docx
from app.formats.markdown import write_markdown
from app.formats.searchable_pdf import write_searchable_pdf
from app.formats.text import write_txt
from app.formats.word_positions import write_word_positions_json
from app.jobs.models import OutputFormat
from app.ocr.base import OcrResult


def _txt(result: OcrResult, out_dir: Path, original_pdf: Path) -> Path:
    return write_txt(result, out_dir)


def _md(result: OcrResult, out_dir: Path, original_pdf: Path) -> Path:
    return write_markdown(result, out_dir)


def _docx(result: OcrResult, out_dir: Path, original_pdf: Path) -> Path:
    return write_docx(result, out_dir)


def _json(result: OcrResult, out_dir: Path, original_pdf: Path) -> Path:
    return write_word_positions_json(result, out_dir)


def _pdf(result: OcrResult, out_dir: Path, original_pdf: Path) -> Path:
    return write_searchable_pdf(result, out_dir, original_pdf=original_pdf)


FORMATTERS: dict[OutputFormat, Callable[[OcrResult, Path, Path], Path]] = {
    OutputFormat.txt: _txt,
    OutputFormat.md: _md,
    OutputFormat.docx: _docx,
    OutputFormat.json: _json,
    OutputFormat.pdf: _pdf,
}
