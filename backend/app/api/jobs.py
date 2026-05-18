from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api.upload import upload_path
from app.config import get_settings
from app.jobs.models import JobRequest, JobState
from app.jobs.runtime import get_store
from app.pipeline.runner import run_job

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("")
async def create_job(req: JobRequest, background: BackgroundTasks) -> dict[str, str]:
    settings = get_settings()
    pdf = upload_path(req.file_id)
    if not pdf.exists():
        raise HTTPException(status_code=404, detail="Unknown file_id")

    import pypdf

    try:
        total = len(pypdf.PdfReader(str(pdf)).pages)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}") from exc
    start, end = req.page_range
    if end > total:
        raise HTTPException(
            status_code=422, detail=f"page_range end {end} exceeds {total} pages"
        )

    store = get_store()
    work_dir = settings.temp_dir / "jobs" / req.file_id
    work_dir.mkdir(parents=True, exist_ok=True)
    state = store.create(work_dir=work_dir, total_pages=end - start + 1, request=req)

    def _runner() -> None:
        try:
            run_job(store=store, job_id=state.job_id, input_pdf=pdf)
        except Exception:
            log.exception("background runner crashed")

    background.add_task(asyncio.to_thread, _runner)
    return {"job_id": state.job_id}


@router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    store = get_store()
    state = store.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return _serialize(state)


def _serialize(state: JobState) -> dict:
    return {
        "job_id": state.job_id,
        "status": state.status.value,
        "stage": state.stage.value,
        "progress_pct": state.progress_pct,
        "pages_done": state.pages_done,
        "total_pages": state.total_pages,
        "active_workers": state.active_workers,
        "warnings": state.warnings,
        "error": (
            {"message": state.error.message, "details": state.error.details}
            if state.error
            else None
        ),
        "outputs": [
            {
                "format": o.format.value,
                "url": f"/api/jobs/{state.job_id}/download/{o.format.value}",
                "size_bytes": o.size_bytes,
            }
            for o in state.outputs
        ],
    }
