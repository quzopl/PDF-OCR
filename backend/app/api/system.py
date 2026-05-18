from fastapi import APIRouter

from app.system_info import get_system_info

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info")
def info() -> dict:
    return get_system_info()
