from __future__ import annotations

import subprocess
from pathlib import Path

import pikepdf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.upload import upload_path

router = APIRouter(prefix="/api", tags=["unlock"])

# qpdf exit codes: 0 = success, 3 = warnings (output still produced), other = failure
_QPDF_OK_CODES = (0, 3)


class UnlockRequest(BaseModel):
    file_id: str = Field(min_length=1)
    password: str = ""


def _qpdf_decrypt(path: Path, password: str) -> None:
    """Remove encryption from PDF in-place via the `qpdf` system binary."""
    cmd = [
        "qpdf",
        f"--password={password}",
        "--decrypt",
        "--replace-input",
        str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="qpdf binary not found on server (install: pacman -S qpdf)",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=422, detail="qpdf timed out") from exc

    if proc.returncode in _QPDF_OK_CODES:
        return

    stderr = (proc.stderr or "").lower()
    if "invalid password" in stderr or "incorrect password" in stderr:
        raise HTTPException(status_code=400, detail="Invalid password")

    raise HTTPException(
        status_code=422,
        detail=f"qpdf failed: {(proc.stderr or '').strip() or 'unknown error'}",
    )


@router.post("/unlock")
def unlock(req: UnlockRequest) -> dict:
    pdf_path = upload_path(req.file_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Unknown file_id")

    _qpdf_decrypt(pdf_path, req.password)

    try:
        with pikepdf.open(str(pdf_path)) as pdf:
            page_count = len(pdf.pages)
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Decrypted but could not read PDF: {exc}"
        ) from exc

    return {
        "file_id": req.file_id,
        "page_count": page_count,
        "size_bytes": pdf_path.stat().st_size,
        "is_encrypted": False,
    }
