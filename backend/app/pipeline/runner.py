from __future__ import annotations

import logging
from pathlib import Path

from app.formats import FORMATTERS
from app.jobs.models import (
    Device,
    Engine,
    JobError,
    JobOutput,
    JobStage,
    JobStatus,
)
from app.jobs.store import JobStore
from app.ocr.base import EngineOptions, OcrEngine
from app.ocr.ocrmypdf_engine import OcrMyPdfEngine
from app.ocr.paddle_engine import PaddleEngine
from app.pipeline.page_range import extract_page_range

log = logging.getLogger(__name__)


def _select_engine(name: Engine) -> OcrEngine:
    if name == Engine.ocrmypdf:
        return OcrMyPdfEngine()
    if name == Engine.paddle:
        return PaddleEngine()
    raise ValueError(f"unknown engine: {name}")


def run_job(*, store: JobStore, job_id: str, input_pdf: Path) -> None:
    state = store.get(job_id)
    if state is None:
        return
    req = state.request
    try:
        store.update(job_id, status=JobStatus.running, stage=JobStage.preprocessing)
        working = state.work_dir / "working.pdf"
        extract_page_range(input_pdf, working, start=req.page_range[0], end=req.page_range[1])

        engine = _select_engine(req.engine)
        use_cuda = req.device == Device.cuda
        opts = EngineOptions(
            languages=[l.value for l in req.languages],
            workers=req.workers,
            use_cuda=use_cuda,
            deskew=req.preprocess.deskew,
            denoise=req.preprocess.denoise,
        )

        store.update(job_id, stage=JobStage.ocr, active_workers=req.workers)

        def _progress(*, pages_done: int, active_workers: int) -> None:
            store.update(job_id, pages_done=pages_done, active_workers=active_workers)

        try:
            result = engine.run(working, opts, state.work_dir / "engine", _progress)
        except Exception as exc:
            if use_cuda and isinstance(engine, PaddleEngine):
                log.warning("CUDA failed, retrying on CPU: %s", exc)
                store.update(
                    job_id,
                    warning="GPU unavailable; ran on CPU.",
                    active_workers=req.workers,
                )
                opts_cpu = EngineOptions(
                    languages=opts.languages,
                    workers=opts.workers,
                    use_cuda=False,
                    deskew=opts.deskew,
                    denoise=opts.denoise,
                )
                result = engine.run(working, opts_cpu, state.work_dir / "engine_cpu", _progress)
            else:
                raise

        store.update(job_id, stage=JobStage.formatting, active_workers=0)
        outputs_dir = state.work_dir / "outputs"
        outputs: list[JobOutput] = []
        for fmt in req.formats:
            formatter = FORMATTERS[fmt]
            sub_dir = outputs_dir / fmt.value
            path = formatter(result, sub_dir, working)
            outputs.append(JobOutput(format=fmt, path=path, size_bytes=path.stat().st_size))
        store.update(job_id, outputs=outputs)
        store.mark_finished(job_id, status=JobStatus.done)
    except Exception as exc:
        log.exception("job %s failed", job_id)
        store.update(job_id, error=JobError(message=str(exc), details=repr(exc)))
        store.mark_finished(job_id, status=JobStatus.failed)
