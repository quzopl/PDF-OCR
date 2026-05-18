from __future__ import annotations

import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import numpy as np
from pdf2image import convert_from_path

from app.ocr.base import EngineOptions, OcrEngine, OcrPage, OcrResult, Word
from app.pipeline.preprocess import preprocess_image

_PADDLE_LANG = {
    "pl": "pl",
    "en": "en",
    "de": "german",
    "fr": "french",
    "es": "es",
    "ru": "ru",
}


def _primary_paddle_lang(languages: list[str]) -> str:
    # PaddleOCR accepts a single language per detector instance; pick the first.
    return _PADDLE_LANG.get(languages[0], "en")


def _ocr_one(
    image_arr: np.ndarray,
    page_number: int,
    width: float,
    height: float,
    lang: str,
    use_gpu: bool,
) -> OcrPage:
    from paddleocr import PaddleOCR  # local import to keep process model clean

    ocr = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=use_gpu, show_log=False)
    raw = ocr.ocr(image_arr, cls=True)
    words: list[Word] = []
    if raw and raw[0]:
        for box, (text, conf) in raw[0]:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            words.append(
                Word(
                    text=text,
                    bbox=(float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))),
                    confidence=float(conf),
                )
            )
    return OcrPage(page_number=page_number, width=width, height=height, words=words)


class PaddleEngine(OcrEngine):
    name = "paddle"

    def run(
        self,
        pdf_path: Path,
        opts: EngineOptions,
        work_dir: Path,
        progress: Callable[..., None],
    ) -> OcrResult:
        work_dir.mkdir(parents=True, exist_ok=True)
        lang = _primary_paddle_lang(opts.languages)
        pil_pages = convert_from_path(str(pdf_path), dpi=300)

        prepared: list[tuple[int, np.ndarray, float, float]] = []
        for idx, pil in enumerate(pil_pages, start=1):
            pil = preprocess_image(pil, deskew=opts.deskew, denoise=opts.denoise)
            prepared.append((idx, np.array(pil), float(pil.width), float(pil.height)))

        total = len(prepared)
        done = 0
        pages: dict[int, OcrPage] = {}
        progress(pages_done=0, active_workers=opts.workers)

        if opts.use_cuda:
            workers = min(opts.workers, 2)
            executor: ThreadPoolExecutor | ProcessPoolExecutor = ThreadPoolExecutor(
                max_workers=workers
            )
        else:
            workers = max(1, opts.workers)
            executor = ProcessPoolExecutor(max_workers=workers)

        try:
            futures = [
                executor.submit(_ocr_one, arr, num, w, h, lang, opts.use_cuda)
                for (num, arr, w, h) in prepared
            ]
            for fut in as_completed(futures):
                page = fut.result()
                pages[page.page_number] = page
                done += 1
                progress(pages_done=done, active_workers=workers)
        finally:
            executor.shutdown(wait=True)

        ordered = [pages[i] for i in sorted(pages.keys())]
        progress(pages_done=total, active_workers=0)
        return OcrResult(
            pages=ordered,
            engine=self.name,
            languages=list(opts.languages),
            raw_searchable_pdf=None,
        )
