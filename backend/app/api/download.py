from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.jobs.models import OutputFormat
from app.jobs.runtime import get_store

_MEDIA = {
    OutputFormat.pdf: "application/pdf",
    OutputFormat.txt: "text/plain; charset=utf-8",
    OutputFormat.md: "text/markdown; charset=utf-8",
    OutputFormat.docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    OutputFormat.json: "application/json",
}

_EXT = {
    OutputFormat.pdf: "pdf",
    OutputFormat.txt: "txt",
    OutputFormat.md: "md",
    OutputFormat.docx: "docx",
    OutputFormat.json: "json",
}

router = APIRouter(prefix="/api/jobs", tags=["download"])


@router.get("/{job_id}/download/{fmt}")
def download(job_id: str, fmt: OutputFormat) -> FileResponse:
    state = get_store().get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    for out in state.outputs:
        if out.format == fmt:
            return FileResponse(
                str(out.path),
                media_type=_MEDIA[fmt],
                filename=f"ocr_{job_id[:8]}.{_EXT[fmt]}",
            )
    raise HTTPException(status_code=404, detail=f"No output for format {fmt.value}")
