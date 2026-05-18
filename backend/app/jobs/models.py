from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, Field, model_validator


class Engine(str, Enum):
    ocrmypdf = "ocrmypdf"
    paddle = "paddle"


class Language(str, Enum):
    pl = "pl"
    en = "en"
    de = "de"
    fr = "fr"
    es = "es"
    ru = "ru"


class OutputFormat(str, Enum):
    pdf = "pdf"
    txt = "txt"
    md = "md"
    docx = "docx"
    json = "json"


class Device(str, Enum):
    cpu = "cpu"
    cuda = "cuda"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class JobStage(str, Enum):
    queued = "queued"
    downloading_models = "downloading_models"
    preprocessing = "preprocessing"
    ocr = "ocr"
    formatting = "formatting"
    finished = "finished"


class Preprocess(BaseModel):
    deskew: bool = False
    denoise: bool = False


class JobRequest(BaseModel):
    file_id: str = Field(min_length=1)
    engine: Engine
    languages: list[Language] = Field(min_length=1)
    page_range: tuple[int, int]
    preprocess: Preprocess
    formats: list[OutputFormat] = Field(min_length=1)
    workers: int = Field(ge=1)
    device: Device

    @model_validator(mode="after")
    def _check_range(self) -> "JobRequest":
        start, end = self.page_range
        if start < 1 or end < start:
            raise ValueError("page_range must satisfy 1 <= start <= end")
        return self


class JobOutput(BaseModel):
    format: OutputFormat
    path: Path
    size_bytes: int


class JobError(BaseModel):
    message: str
    details: str | None = None


class JobState(BaseModel):
    job_id: str
    status: JobStatus
    stage: JobStage
    progress_pct: float = 0.0
    pages_done: int = 0
    total_pages: int
    active_workers: int = 0
    warnings: list[str] = Field(default_factory=list)
    error: JobError | None = None
    outputs: list[JobOutput] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: AwareDatetime | None = None
    work_dir: Path
    request: JobRequest
