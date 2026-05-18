from __future__ import annotations

import uuid
from pathlib import Path

import pikepdf
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings

router = APIRouter(prefix="/api", tags=["upload"])


def _probe(path: Path) -> tuple[bool, int]:
    """Open the PDF; return (is_encrypted, page_count). page_count=0 if locked."""
    try:
        with pikepdf.open(str(path)) as pdf:
            return False, len(pdf.pages)
    except pikepdf.PasswordError:
        return True, 0


@router.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    settings = get_settings()
    if file.content_type not in {"application/pdf", "application/x-pdf"} and not (
        file.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    file_id = uuid.uuid4().hex
    target_dir = settings.temp_dir / "uploads"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{file_id}.pdf"

    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    with target.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"PDF exceeds {settings.max_upload_mb} MB")
            out.write(chunk)

    try:
        is_encrypted, page_count = _probe(target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not open PDF: {exc}") from exc

    if not is_encrypted and page_count == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="PDF has no pages")

    return {
        "file_id": file_id,
        "page_count": page_count,
        "size_bytes": size,
        "is_encrypted": is_encrypted,
    }


def upload_path(file_id: str) -> Path:
    return get_settings().temp_dir / "uploads" / f"{file_id}.pdf"
