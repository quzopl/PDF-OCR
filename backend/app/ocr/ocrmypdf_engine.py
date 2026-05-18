from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

import pdfplumber

from app.ocr.base import EngineOptions, OcrEngine, OcrPage, OcrResult, Word

_PADDLE_TO_TESS = {
    "pl": "pol",
    "en": "eng",
    "de": "deu",
    "fr": "fra",
    "es": "spa",
    "ru": "rus",
}


class OcrMyPdfEngine(OcrEngine):
    name = "ocrmypdf"

    def run(
        self,
        pdf_path: Path,
        opts: EngineOptions,
        work_dir: Path,
        progress: Callable[..., None],
    ) -> OcrResult:
        work_dir.mkdir(parents=True, exist_ok=True)
        out_pdf = work_dir / "ocr_output.pdf"
        sidecar = work_dir / "ocr_sidecar.txt"
        langs = "+".join(_PADDLE_TO_TESS.get(l, l) for l in opts.languages)
        cmd = [
            "ocrmypdf",
            "--force-ocr",
            "--language",
            langs,
            "--jobs",
            str(opts.workers),
            "--sidecar",
            str(sidecar),
            "--output-type",
            "pdf",
        ]
        if opts.deskew:
            cmd.append("--deskew")
        if opts.denoise:
            cmd.append("--clean")
        cmd.extend([str(pdf_path), str(out_pdf)])

        progress(pages_done=0, active_workers=opts.workers)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=None)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"ocrmypdf failed: {exc.stderr or exc.stdout}") from exc

        result = self._parse_output(out_pdf, opts.languages)
        progress(pages_done=len(result.pages), active_workers=0)
        return result

    def _parse_output(self, out_pdf: Path, languages: list[str]) -> OcrResult:
        pages: list[OcrPage] = []
        with pdfplumber.open(str(out_pdf)) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                words = [
                    Word(
                        text=w["text"],
                        bbox=(
                            float(w["x0"]),
                            float(w["top"]),
                            float(w["x1"]),
                            float(w["bottom"]),
                        ),
                        confidence=None,
                    )
                    for w in page.extract_words() or []
                ]
                pages.append(
                    OcrPage(
                        page_number=idx,
                        width=float(page.width),
                        height=float(page.height),
                        words=words,
                    )
                )
        return OcrResult(
            pages=pages,
            engine=self.name,
            languages=list(languages),
            raw_searchable_pdf=out_pdf,
        )
