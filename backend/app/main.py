import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import download as download_api
from app.api import jobs as jobs_api
from app.api import system as system_api
from app.api import unlock as unlock_api
from app.api import upload as upload_api
from app.config import get_settings
from app.jobs.runtime import get_store


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    _configure_logging(settings.log_level)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    store = get_store()

    stop = asyncio.Event()

    async def _sweep() -> None:
        while not stop.is_set():
            try:
                store.sweep_expired()
            except Exception:
                logging.exception("sweeper failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=60)
            except asyncio.TimeoutError:
                continue

    task = asyncio.create_task(_sweep())
    try:
        yield
    finally:
        stop.set()
        await task


app = FastAPI(title="OCR PDF API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3101", "http://localhost:3101"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_api.router)
app.include_router(unlock_api.router)
app.include_router(system_api.router)
app.include_router(jobs_api.router)
app.include_router(download_api.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
