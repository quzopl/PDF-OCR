from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol


@dataclass
class Word:
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 (points)
    confidence: float | None = None


@dataclass
class OcrPage:
    page_number: int  # 1-indexed in original PDF
    width: float
    height: float
    words: list[Word] = field(default_factory=list)


@dataclass
class OcrResult:
    pages: list[OcrPage]
    engine: str
    languages: list[str]
    raw_searchable_pdf: Path | None = None


class ProgressCallback(Protocol):
    def __call__(self, *, pages_done: int, active_workers: int) -> None: ...


@dataclass
class EngineOptions:
    languages: list[str]
    workers: int
    use_cuda: bool
    deskew: bool
    denoise: bool


class OcrEngine(ABC):
    name: str = "base"

    @abstractmethod
    def run(
        self,
        pdf_path: Path,
        opts: EngineOptions,
        work_dir: Path,
        progress: Callable[..., None],
    ) -> OcrResult:
        """Run OCR. Must call progress(pages_done=N, active_workers=M) as it advances."""
