from __future__ import annotations

import pikepdf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.upload import upload_path

router = APIRouter(prefix="/api", tags=["unlock"])


class UnlockRequest(BaseModel):
    file_id: str = Field(min_length=1)
    password: str = ""


@router.post("/unlock")
def unlock(req: UnlockRequest) -> dict:
    pdf_path = upload_path(req.file_id)
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Unknown file_id")

    try:
        pdf = pikepdf.open(str(pdf_path), password=req.password, allow_overwriting_input=True)
    except pikepdf.PasswordError:
        raise HTTPException(status_code=400, detail="Invalid password")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not open PDF: {exc}") from exc

    try:
        pdf.save(str(pdf_path))
        page_count = len(pdf.pages)
    finally:
        pdf.close()

    return {
        "file_id": req.file_id,
        "page_count": page_count,
        "size_bytes": pdf_path.stat().st_size,
        "is_encrypted": False,
    }
