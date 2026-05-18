# OCR PDF App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web app that performs OCR on a single PDF with a polished GUI, selectable engine (OCRmyPDF or PaddleOCR), per-page parallelism, optional CUDA, and multiple output formats (searchable PDF, TXT, MD, DOCX, JSON with word positions).

**Architecture:** Two processes — FastAPI on `127.0.0.1:8114` and Next.js on `127.0.0.1:3101`. Frontend uploads a PDF, POSTs a job, and polls a status endpoint at 1 Hz until results are downloadable. Jobs and working files live in memory / `/tmp` and are TTL-swept; no DB, no auth.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pypdf, pdf2image, pikepdf, pdfplumber, python-docx, opencv-python-headless, ocrmypdf, paddleocr (+ optional paddlepaddle-gpu), uv. Frontend: Next.js 15, React 19, TypeScript, Tailwind 4, shadcn/ui, framer-motion, react-dropzone, sonner, vitest, Playwright.

---

## File Structure

### Backend (`backend/`)

| File | Responsibility |
|---|---|
| `pyproject.toml` | uv project, deps, optional `[gpu]` extra, ruff config |
| `app/main.py` | FastAPI app, CORS, lifespan (start TTL sweeper), router include |
| `app/config.py` | Settings (pydantic-settings): ports, limits, TTL, temp dir, max workers |
| `app/system_info.py` | Detect CPU/RAM/GPU once at startup, cache result |
| `app/jobs/models.py` | Pydantic enums + DTOs: `JobStatus`, `JobStage`, `JobOutput`, `JobState`, `JobRequest` |
| `app/jobs/store.py` | Thread-safe in-memory job dict + TTL sweep task |
| `app/ocr/base.py` | `Word`, `OcrPage`, `OcrResult` dataclasses + `OcrEngine` ABC |
| `app/ocr/ocrmypdf_engine.py` | OCRmyPDF subprocess + parse sidecar text + extract bboxes from output PDF |
| `app/ocr/paddle_engine.py` | PaddleOCR engine — CPU (ProcessPool) and CUDA (ThreadPool) paths |
| `app/pipeline/page_range.py` | Pure: extract `[start, end]` from input PDF → working PDF |
| `app/pipeline/preprocess.py` | Pure: deskew + denoise on a PIL image (used only for Paddle path) |
| `app/pipeline/runner.py` | Orchestrate range → preprocess → engine → formatters with progress callbacks |
| `app/formats/__init__.py` | `FORMATTERS` registry (format name → callable) |
| `app/formats/text.py` | OcrResult → plain `.txt` |
| `app/formats/searchable_pdf.py` | OcrResult → searchable PDF (passthrough for OCRmyPDF, overlay for Paddle) |
| `app/formats/markdown.py` | OcrResult → `.md` with `---` page separators |
| `app/formats/docx.py` | OcrResult → `.docx` via python-docx |
| `app/formats/word_positions.py` | OcrResult → JSON of pages with word boxes |
| `app/api/upload.py` | `POST /api/upload` |
| `app/api/jobs.py` | `POST /api/jobs`, `GET /api/jobs/{id}` |
| `app/api/download.py` | `GET /api/jobs/{id}/download/{format}` |
| `app/api/system.py` | `GET /api/system/info` |
| `tests/conftest.py` | Pytest fixtures (temp dirs, sample PDFs) |
| `tests/fixtures/` | Sample PDFs |

### Frontend (`frontend/`)

| File | Responsibility |
|---|---|
| `package.json`, `tsconfig.json`, `next.config.mjs`, `tailwind.config.ts`, `postcss.config.mjs`, `components.json` | Toolchain |
| `app/layout.tsx` | Root layout: dark theme, font, `Toaster` |
| `app/page.tsx` | Single-page flow: dropzone → options → progress → results |
| `app/globals.css` | Tailwind + shadcn theme tokens |
| `lib/api.ts` | Typed fetch wrappers; `BASE_URL` from `NEXT_PUBLIC_API_URL` |
| `lib/types.ts` | API DTOs mirroring backend |
| `lib/format-matrix.ts` | Pure: per-engine capability/quality matrix + warnings |
| `hooks/use-job-status.ts` | Polls job status at 1 Hz, exposes `status`, `progress`, `outputs`, `error`, `stop()` |
| `components/hardware-chip.tsx` | Header chip + popover (CPU/RAM/GPU) |
| `components/dropzone.tsx` | Animated drop area, uploads → returns `{file_id, page_count}` |
| `components/job-options.tsx` | Form: engine, languages, page range, preprocess, formats, workers, device |
| `components/progress-panel.tsx` | Progress bar + stage label + workers count |
| `components/results-panel.tsx` | Download buttons per produced output |
| `components/ui/*` | shadcn primitives (generated via CLI) |
| `tests/format-matrix.test.ts` | Vitest unit tests |
| `tests/api.test.ts` | Vitest unit tests for `lib/api.ts` |
| `e2e/upload-flow.spec.ts` | Playwright smoke test |

### Repo root

| File | Responsibility |
|---|---|
| `Makefile` | `make dev`, `make test`, `make install` |
| `.env.example` | Documented env vars |
| `README.md` | Setup instructions for Manjaro/Arch |

---

## Task 1: Repo scaffolding

**Files:**
- Create: `Makefile`
- Create: `.env.example`
- Create: `README.md`
- Create: `backend/` (directory)
- Create: `frontend/` (directory)

- [ ] **Step 1: Create directories**

```bash
mkdir -p backend/app/{api,jobs,ocr,pipeline,formats} backend/tests/fixtures frontend
```

- [ ] **Step 2: Write `.env.example`**

```dotenv
# Backend
API_HOST=127.0.0.1
API_PORT=8114
OCR_TEMP_DIR=/tmp/ocrapp
OCR_JOB_TTL_SECONDS=3600
OCR_MAX_UPLOAD_MB=200
OCR_MAX_PAGES=500
OCR_JOB_TIMEOUT_SECONDS=1800
OCR_MAX_WORKERS=
OCR_LOG_LEVEL=INFO

# Frontend
FRONT_PORT=3101
NEXT_PUBLIC_API_URL=http://127.0.0.1:8114
```

- [ ] **Step 3: Write `Makefile`**

```makefile
.PHONY: install dev backend frontend test test-backend test-frontend test-e2e clean

install:
	cd backend && uv sync
	cd frontend && pnpm install

dev:
	@echo "Starting backend on :8114 and frontend on :3101"
	@trap 'kill 0' INT; \
	  (cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8114 --reload 2>&1 | sed 's/^/[api] /') & \
	  (cd frontend && pnpm dev -p 3101 2>&1 | sed 's/^/[web] /') & \
	  wait

backend:
	cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8114 --reload

frontend:
	cd frontend && pnpm dev -p 3101

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest -q

test-frontend:
	cd frontend && pnpm test

test-e2e:
	cd frontend && pnpm exec playwright test

clean:
	rm -rf /tmp/ocrapp backend/.pytest_cache backend/.ruff_cache
```

- [ ] **Step 4: Write `README.md`**

````markdown
# OCR PDF

Local web app that OCRs a PDF and produces searchable PDF, TXT, Markdown, DOCX, and JSON with word positions. Two engines (OCRmyPDF, PaddleOCR), per-page parallelism, optional CUDA.

## System dependencies (Manjaro / Arch)

```bash
sudo pacman -S tesseract \
  tesseract-data-pol tesseract-data-eng tesseract-data-deu \
  tesseract-data-fra tesseract-data-spa tesseract-data-rus \
  ghostscript unpaper poppler nodejs python uv
# Optional for CUDA:
sudo pacman -S cuda cudnn
```

## Install

```bash
cp .env.example .env
make install        # uv sync + pnpm install
```

For CUDA: `cd backend && uv sync --extra gpu`.

## Run

```bash
make dev
# open http://127.0.0.1:3101
```

## Test

```bash
make test           # pytest + vitest
make test-e2e       # Playwright
```
````

- [ ] **Step 5: Commit**

```bash
git add Makefile .env.example README.md backend frontend
git commit -m "chore: scaffold repo (Makefile, env, dirs)"
```

---

## Task 2: Backend Python project

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write `backend/pyproject.toml`**

```toml
[project]
name = "ocr-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.34",
  "pydantic>=2.9",
  "pydantic-settings>=2.6",
  "python-multipart>=0.0.20",
  "pypdf>=5.1",
  "pdf2image>=1.17",
  "pikepdf>=9.4",
  "pdfplumber>=0.11",
  "python-docx>=1.1",
  "opencv-python-headless>=4.10",
  "numpy>=2.0",
  "psutil>=6.1",
  "structlog>=24.4",
  "Pillow>=11.0",
  "reportlab>=4.2",
  "ocrmypdf>=16.8",
  "paddleocr>=2.9",
  "paddlepaddle>=2.6",
]

[project.optional-dependencies]
gpu = ["paddlepaddle-gpu>=2.6"]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "ruff>=0.7",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write `backend/app/__init__.py`**

```python
```

- [ ] **Step 3: Write `backend/tests/__init__.py`**

```python
```

- [ ] **Step 4: Write the failing test — `backend/tests/test_health.py`**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 5: Run the test and verify it fails**

```bash
cd backend && uv sync --extra dev && uv run pytest tests/test_health.py -v
```

Expected: ModuleNotFoundError or 404 (no `app.main` yet).

- [ ] **Step 6: Write `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="OCR PDF API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3101", "http://localhost:3101"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: Re-run the test**

```bash
cd backend && uv run pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app backend/tests
git commit -m "feat(backend): bootstrap FastAPI app with health endpoint"
```

---

## Task 3: Settings (`app/config.py`)

**Files:**
- Create: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
import os
from pathlib import Path

from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.api_port == 8114
    assert s.max_upload_mb == 200
    assert s.max_pages == 500
    assert s.job_ttl_seconds == 3600
    assert s.job_timeout_seconds == 1800
    assert s.temp_dir == Path("/tmp/ocrapp")
    assert s.max_workers >= 1  # auto-detected


def test_env_override(monkeypatch):
    monkeypatch.setenv("OCR_MAX_UPLOAD_MB", "50")
    monkeypatch.setenv("OCR_MAX_WORKERS", "4")
    s = Settings(_env_file=None)
    assert s.max_upload_mb == 50
    assert s.max_workers == 4
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_config.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Write `backend/app/config.py`**

```python
import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OCR_", env_file=".env", extra="ignore")

    api_host: str = "127.0.0.1"
    api_port: int = 8114
    temp_dir: Path = Path("/tmp/ocrapp")
    job_ttl_seconds: int = 3600
    job_timeout_seconds: int = 1800
    max_upload_mb: int = 200
    max_pages: int = 500
    max_workers: int = Field(default_factory=lambda: os.cpu_count() or 1)
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(backend): settings module with env overrides"
```

---

## Task 4: System info (`app/system_info.py`)

**Files:**
- Create: `backend/app/system_info.py`
- Test: `backend/tests/test_system_info.py`

- [ ] **Step 1: Write the failing test**

```python
from app.system_info import get_system_info


def test_system_info_shape():
    info = get_system_info()
    assert info["cpu"]["count"] >= 1
    assert isinstance(info["cpu"]["model"], str)
    assert info["ram"]["total_gb"] > 0
    assert info["ram"]["available_gb"] > 0
    assert "cuda_available" in info["gpu"]
    assert "devices" in info["gpu"]
    assert isinstance(info["gpu"]["devices"], list)
    assert "paddle_gpu_installed" in info["gpu"]
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_system_info.py -v
```

- [ ] **Step 3: Write `backend/app/system_info.py`**

```python
from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from importlib.util import find_spec
from typing import Any

import psutil


def _cpu_model() -> str:
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "unknown"


def _detect_paddle_gpu() -> bool:
    return find_spec("paddle") is not None and _paddle_cuda_compiled()


def _paddle_cuda_compiled() -> bool:
    try:
        import paddle  # type: ignore

        return bool(paddle.device.is_compiled_with_cuda())
    except Exception:
        return False


def _detect_gpus() -> list[dict[str, Any]]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return []
    devices: list[dict[str, Any]] = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 4:
            continue
        try:
            devices.append(
                {
                    "id": int(parts[0]),
                    "name": parts[1],
                    "vram_gb": round(int(parts[2]) / 1024, 2),
                    "driver": parts[3],
                }
            )
        except ValueError:
            continue
    return devices


@lru_cache(maxsize=1)
def get_system_info() -> dict[str, Any]:
    vm = psutil.virtual_memory()
    devices = _detect_gpus()
    paddle_gpu = _detect_paddle_gpu()
    return {
        "cpu": {
            "count": os.cpu_count() or 1,
            "model": _cpu_model(),
        },
        "ram": {
            "total_gb": round(vm.total / (1024**3), 2),
            "available_gb": round(vm.available / (1024**3), 2),
        },
        "gpu": {
            "cuda_available": bool(devices) and paddle_gpu,
            "devices": devices,
            "paddle_gpu_installed": paddle_gpu,
        },
    }
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_system_info.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/system_info.py backend/tests/test_system_info.py
git commit -m "feat(backend): system info detection (CPU, RAM, GPU)"
```

---

## Task 5: Job models (`app/jobs/models.py`)

**Files:**
- Create: `backend/app/jobs/__init__.py`
- Create: `backend/app/jobs/models.py`
- Test: `backend/tests/test_job_models.py`

- [ ] **Step 1: Create `backend/app/jobs/__init__.py`**

```python
```

- [ ] **Step 2: Write the failing test**

```python
import pytest
from pydantic import ValidationError

from app.jobs.models import (
    Device,
    Engine,
    JobRequest,
    JobStage,
    JobStatus,
    Language,
    OutputFormat,
    Preprocess,
)


def test_languages_enum():
    assert {l.value for l in Language} == {"pl", "en", "de", "fr", "es", "ru"}


def test_engine_enum():
    assert {e.value for e in Engine} == {"ocrmypdf", "paddle"}


def test_output_format_enum():
    assert {f.value for f in OutputFormat} == {"pdf", "txt", "md", "docx", "json"}


def test_job_status_terminal():
    assert JobStatus.done in {JobStatus.done, JobStatus.failed}


def test_job_stages():
    assert JobStage.ocr.value == "ocr"
    assert JobStage.formatting.value == "formatting"


def test_job_request_minimal():
    req = JobRequest(
        file_id="abc",
        engine=Engine.ocrmypdf,
        languages=[Language.pl],
        page_range=(1, 3),
        preprocess=Preprocess(deskew=True, denoise=False),
        formats=[OutputFormat.pdf, OutputFormat.txt],
        workers=4,
        device=Device.cpu,
    )
    assert req.page_range == (1, 3)


def test_job_request_rejects_inverted_range():
    with pytest.raises(ValidationError):
        JobRequest(
            file_id="abc",
            engine=Engine.ocrmypdf,
            languages=[Language.pl],
            page_range=(5, 2),
            preprocess=Preprocess(deskew=False, denoise=False),
            formats=[OutputFormat.txt],
            workers=1,
            device=Device.cpu,
        )


def test_job_request_rejects_empty_languages():
    with pytest.raises(ValidationError):
        JobRequest(
            file_id="abc",
            engine=Engine.ocrmypdf,
            languages=[],
            page_range=(1, 1),
            preprocess=Preprocess(deskew=False, denoise=False),
            formats=[OutputFormat.txt],
            workers=1,
            device=Device.cpu,
        )


def test_job_request_rejects_empty_formats():
    with pytest.raises(ValidationError):
        JobRequest(
            file_id="abc",
            engine=Engine.ocrmypdf,
            languages=[Language.pl],
            page_range=(1, 1),
            preprocess=Preprocess(deskew=False, denoise=False),
            formats=[],
            workers=1,
            device=Device.cpu,
        )
```

- [ ] **Step 3: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_job_models.py -v
```

- [ ] **Step 4: Write `backend/app/jobs/models.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


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
    file_id: str
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
    finished_at: datetime | None = None
    work_dir: Path
    request: JobRequest
```

- [ ] **Step 5: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_job_models.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/jobs backend/tests/test_job_models.py
git commit -m "feat(backend): job models (enums, request, state)"
```

---

## Task 6: Job store (`app/jobs/store.py`)

**Files:**
- Create: `backend/app/jobs/store.py`
- Test: `backend/tests/test_job_store.py`

- [ ] **Step 1: Write the failing test**

```python
import asyncio
import time
from pathlib import Path

import pytest

from app.jobs.models import (
    Device,
    Engine,
    JobRequest,
    JobStage,
    JobStatus,
    Language,
    OutputFormat,
    Preprocess,
)
from app.jobs.store import JobStore


def _make_request() -> JobRequest:
    return JobRequest(
        file_id="f1",
        engine=Engine.ocrmypdf,
        languages=[Language.pl],
        page_range=(1, 2),
        preprocess=Preprocess(),
        formats=[OutputFormat.txt],
        workers=1,
        device=Device.cpu,
    )


def test_create_and_get(tmp_path: Path):
    store = JobStore(ttl_seconds=60)
    state = store.create(work_dir=tmp_path / "j1", total_pages=2, request=_make_request())
    fetched = store.get(state.job_id)
    assert fetched is not None
    assert fetched.status == JobStatus.pending


def test_update_status(tmp_path: Path):
    store = JobStore(ttl_seconds=60)
    state = store.create(work_dir=tmp_path / "j1", total_pages=2, request=_make_request())
    store.update(state.job_id, status=JobStatus.running, stage=JobStage.ocr, pages_done=1)
    s = store.get(state.job_id)
    assert s.status == JobStatus.running
    assert s.pages_done == 1
    assert s.progress_pct == 50.0


def test_missing_returns_none():
    store = JobStore(ttl_seconds=60)
    assert store.get("nope") is None


@pytest.mark.asyncio
async def test_ttl_sweep(tmp_path: Path):
    store = JobStore(ttl_seconds=0)  # immediate eligibility once finished
    state = store.create(work_dir=tmp_path / "j1", total_pages=1, request=_make_request())
    store.mark_finished(state.job_id, status=JobStatus.done)
    # Make work dir exist so cleanup has something to remove
    (tmp_path / "j1").mkdir()
    await asyncio.sleep(0.01)
    removed = store.sweep_expired(now=time.time() + 1)
    assert state.job_id in removed
    assert store.get(state.job_id) is None
    assert not (tmp_path / "j1").exists()
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_job_store.py -v
```

- [ ] **Step 3: Write `backend/app/jobs/store.py`**

```python
from __future__ import annotations

import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.jobs.models import JobError, JobRequest, JobStage, JobState, JobStatus


class JobStore:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._jobs: dict[str, JobState] = {}
        self._finished_at_monotonic: dict[str, float] = {}

    def create(self, *, work_dir: Path, total_pages: int, request: JobRequest) -> JobState:
        job_id = uuid.uuid4().hex
        state = JobState(
            job_id=job_id,
            status=JobStatus.pending,
            stage=JobStage.queued,
            total_pages=total_pages,
            work_dir=work_dir,
            request=request,
        )
        with self._lock:
            self._jobs[job_id] = state
        return state

    def get(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        stage: JobStage | None = None,
        pages_done: int | None = None,
        active_workers: int | None = None,
        warning: str | None = None,
        outputs: list | None = None,
        error: JobError | None = None,
    ) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return
            if status is not None:
                state.status = status
            if stage is not None:
                state.stage = stage
            if pages_done is not None:
                state.pages_done = pages_done
                state.progress_pct = (
                    round(pages_done / state.total_pages * 100, 1) if state.total_pages else 0.0
                )
            if active_workers is not None:
                state.active_workers = active_workers
            if warning is not None:
                state.warnings.append(warning)
            if outputs is not None:
                state.outputs = outputs
            if error is not None:
                state.error = error

    def mark_finished(self, job_id: str, *, status: JobStatus) -> None:
        with self._lock:
            state = self._jobs.get(job_id)
            if state is None:
                return
            state.status = status
            state.stage = JobStage.finished
            state.finished_at = datetime.now(timezone.utc)
            if status == JobStatus.done:
                state.progress_pct = 100.0
                state.pages_done = state.total_pages
            state.active_workers = 0
            self._finished_at_monotonic[job_id] = time.time()

    def all_finished(self) -> Iterable[JobState]:
        with self._lock:
            return [s for s in self._jobs.values() if s.finished_at is not None]

    def sweep_expired(self, *, now: float | None = None) -> list[str]:
        cutoff = (now or time.time()) - self._ttl
        removed: list[str] = []
        with self._lock:
            for jid, finished_at in list(self._finished_at_monotonic.items()):
                if finished_at <= cutoff:
                    state = self._jobs.pop(jid, None)
                    self._finished_at_monotonic.pop(jid, None)
                    if state is not None and state.work_dir.exists():
                        shutil.rmtree(state.work_dir, ignore_errors=True)
                    removed.append(jid)
        return removed
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_job_store.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/jobs/store.py backend/tests/test_job_store.py
git commit -m "feat(backend): in-memory job store with TTL sweep"
```

---

## Task 7: OCR base types (`app/ocr/base.py`)

**Files:**
- Create: `backend/app/ocr/__init__.py`
- Create: `backend/app/ocr/base.py`
- Test: `backend/tests/test_ocr_base.py`

- [ ] **Step 1: Create `backend/app/ocr/__init__.py`**

```python
```

- [ ] **Step 2: Write the failing test**

```python
from app.ocr.base import OcrPage, OcrResult, Word


def test_word_dataclass():
    w = Word(text="Cześć", bbox=(0.0, 0.0, 10.0, 5.0), confidence=0.97)
    assert w.text == "Cześć"
    assert w.bbox == (0.0, 0.0, 10.0, 5.0)


def test_ocr_result_iteration():
    page = OcrPage(page_number=1, width=595.0, height=842.0, words=[])
    result = OcrResult(pages=[page], engine="paddle", languages=["pl"])
    assert result.pages[0].page_number == 1
    assert result.raw_searchable_pdf is None
```

- [ ] **Step 3: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_ocr_base.py -v
```

- [ ] **Step 4: Write `backend/app/ocr/base.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol


@dataclass
class Word:
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 (points)
    confidence: float | None = None


@dataclass
class OcrPage:
    page_number: int  # 1-indexed in original PDF
    width: float
    height: float
    words: list[Word] = field(default_factory=list)


@dataclass
class OcrResult:
    pages: list[OcrPage]
    engine: str
    languages: list[str]
    raw_searchable_pdf: Path | None = None


class ProgressCallback(Protocol):
    def __call__(self, *, pages_done: int, active_workers: int) -> None: ...


@dataclass
class EngineOptions:
    languages: list[str]
    workers: int
    use_cuda: bool
    deskew: bool
    denoise: bool


class OcrEngine(ABC):
    name: str = "base"

    @abstractmethod
    def run(
        self,
        pdf_path: Path,
        opts: EngineOptions,
        work_dir: Path,
        progress: Callable[..., None],
    ) -> OcrResult:
        """Run OCR. Must call progress(pages_done=N, active_workers=M) as it advances."""
```

- [ ] **Step 5: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_ocr_base.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/ocr backend/tests/test_ocr_base.py
git commit -m "feat(backend): OCR base types and engine ABC"
```

---

## Task 8: Page-range pipeline (`app/pipeline/page_range.py`)

**Files:**
- Create: `backend/app/pipeline/__init__.py`
- Create: `backend/app/pipeline/page_range.py`
- Test: `backend/tests/test_page_range.py`
- Create: `backend/tests/fixtures/multipage.pdf` (generated by fixture below)

- [ ] **Step 1: Create `backend/app/pipeline/__init__.py`**

```python
```

- [ ] **Step 2: Write `backend/tests/conftest.py`** (shared fixtures)

```python
from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _ensure_fixtures() -> None:
    FIXTURE_DIR.mkdir(exist_ok=True)
    multipage = FIXTURE_DIR / "multipage.pdf"
    if not multipage.exists():
        c = canvas.Canvas(str(multipage), pagesize=A4)
        for i in range(1, 11):
            c.setFont("Helvetica", 24)
            c.drawString(72, 800, f"Page {i}")
            c.drawString(72, 760, f"Marker-{i}")
            c.showPage()
        c.save()
    text = FIXTURE_DIR / "text_simple.pdf"
    if not text.exists():
        c = canvas.Canvas(str(text), pagesize=A4)
        c.setFont("Helvetica", 18)
        c.drawString(72, 800, "Hello world OCR test")
        c.showPage()
        c.save()


@pytest.fixture
def multipage_pdf() -> Path:
    return FIXTURE_DIR / "multipage.pdf"


@pytest.fixture
def text_pdf() -> Path:
    return FIXTURE_DIR / "text_simple.pdf"
```

- [ ] **Step 3: Write the failing test**

```python
from pathlib import Path

import pypdf

from app.pipeline.page_range import extract_page_range


def test_extract_subset(tmp_path: Path, multipage_pdf: Path):
    out = tmp_path / "out.pdf"
    extract_page_range(multipage_pdf, out, start=3, end=5)
    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) == 3


def test_extract_full(tmp_path: Path, multipage_pdf: Path):
    out = tmp_path / "out.pdf"
    extract_page_range(multipage_pdf, out, start=1, end=10)
    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) == 10


def test_extract_out_of_range(tmp_path: Path, multipage_pdf: Path):
    out = tmp_path / "out.pdf"
    import pytest

    with pytest.raises(ValueError):
        extract_page_range(multipage_pdf, out, start=1, end=99)
```

- [ ] **Step 4: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_page_range.py -v
```

- [ ] **Step 5: Write `backend/app/pipeline/page_range.py`**

```python
from __future__ import annotations

from pathlib import Path

import pypdf


def extract_page_range(src: Path, dst: Path, *, start: int, end: int) -> None:
    """Write a PDF containing pages [start, end] (1-indexed, inclusive)."""
    reader = pypdf.PdfReader(str(src))
    total = len(reader.pages)
    if start < 1 or end < start or end > total:
        raise ValueError(f"invalid page range [{start},{end}] for PDF with {total} pages")
    writer = pypdf.PdfWriter()
    for i in range(start - 1, end):
        writer.add_page(reader.pages[i])
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as f:
        writer.write(f)
```

- [ ] **Step 6: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_page_range.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/pipeline backend/tests/test_page_range.py backend/tests/conftest.py
git commit -m "feat(backend): page-range extraction pipeline step"
```

---

## Task 9: Preprocess pipeline (`app/pipeline/preprocess.py`)

**Files:**
- Create: `backend/app/pipeline/preprocess.py`
- Test: `backend/tests/test_preprocess.py`

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from PIL import Image

from app.pipeline.preprocess import preprocess_image


def _checkerboard(size: int = 200) -> Image.Image:
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    arr[::20, :, :] = 255
    return Image.fromarray(arr)


def test_noop_when_both_off():
    img = _checkerboard()
    out = preprocess_image(img, deskew=False, denoise=False)
    assert out.size == img.size
    assert np.array_equal(np.array(out), np.array(img))


def test_returns_pil_image():
    img = _checkerboard()
    out = preprocess_image(img, deskew=True, denoise=True)
    assert isinstance(out, Image.Image)
    assert out.size == img.size
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_preprocess.py -v
```

- [ ] **Step 3: Write `backend/app/pipeline/preprocess.py`**

```python
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def preprocess_image(img: Image.Image, *, deskew: bool, denoise: bool) -> Image.Image:
    if not deskew and not denoise:
        return img
    arr = np.array(img.convert("RGB"))
    if denoise:
        arr = cv2.fastNlMeansDenoisingColored(arr, None, 5, 5, 7, 21)
    if deskew:
        arr = _deskew(arr)
    return Image.fromarray(arr)


def _deskew(arr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.size == 0:
        return arr
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.1:
        return arr
    (h, w) = arr.shape[:2]
    m = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(
        arr, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_preprocess.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/preprocess.py backend/tests/test_preprocess.py
git commit -m "feat(backend): image preprocessing (deskew/denoise)"
```

---

## Task 10: OCRmyPDF engine

**Files:**
- Create: `backend/app/ocr/ocrmypdf_engine.py`
- Test: `backend/tests/test_ocrmypdf_engine.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from app.ocr.base import EngineOptions
from app.ocr.ocrmypdf_engine import OcrMyPdfEngine

pytestmark = pytest.mark.skipif(
    not __import__("shutil").which("tesseract"), reason="tesseract not installed"
)


def test_runs_on_text_pdf(tmp_path: Path, text_pdf: Path):
    progress_calls = []

    def progress(*, pages_done: int, active_workers: int) -> None:
        progress_calls.append((pages_done, active_workers))

    engine = OcrMyPdfEngine()
    opts = EngineOptions(
        languages=["eng"], workers=1, use_cuda=False, deskew=False, denoise=False
    )
    result = engine.run(text_pdf, opts, tmp_path, progress)

    assert len(result.pages) == 1
    assert result.raw_searchable_pdf is not None
    assert result.raw_searchable_pdf.exists()
    text = " ".join(w.text for w in result.pages[0].words).lower()
    assert "hello" in text
    assert progress_calls, "engine must report progress"
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_ocrmypdf_engine.py -v
```

- [ ] **Step 3: Write `backend/app/ocr/ocrmypdf_engine.py`**

```python
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
```

- [ ] **Step 4: Run test, verify PASS (or skip if tesseract missing)**

```bash
cd backend && uv run pytest tests/test_ocrmypdf_engine.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/ocr/ocrmypdf_engine.py backend/tests/test_ocrmypdf_engine.py
git commit -m "feat(backend): OCRmyPDF engine integration"
```

---

## Task 11: PaddleOCR engine

**Files:**
- Create: `backend/app/ocr/paddle_engine.py`
- Test: `backend/tests/test_paddle_engine.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from app.ocr.base import EngineOptions
from app.ocr.paddle_engine import PaddleEngine

pytestmark = pytest.mark.skipif(
    not __import__("importlib.util").util.find_spec("paddleocr"),
    reason="paddleocr not installed",
)


def test_runs_on_text_pdf(tmp_path: Path, text_pdf: Path):
    calls: list[tuple[int, int]] = []

    def progress(*, pages_done: int, active_workers: int) -> None:
        calls.append((pages_done, active_workers))

    engine = PaddleEngine()
    opts = EngineOptions(
        languages=["en"], workers=1, use_cuda=False, deskew=False, denoise=False
    )
    result = engine.run(text_pdf, opts, tmp_path, progress)
    assert len(result.pages) == 1
    text = " ".join(w.text for w in result.pages[0].words).lower()
    assert "hello" in text
    assert any(p == 1 for p, _ in calls)
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_paddle_engine.py -v
```

- [ ] **Step 3: Write `backend/app/ocr/paddle_engine.py`**

```python
from __future__ import annotations

import threading
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import numpy as np
from pdf2image import convert_from_path

from app.ocr.base import EngineOptions, OcrEngine, OcrPage, OcrResult, Word
from app.pipeline.preprocess import preprocess_image

_PADDLE_LANG = {
    "pl": "pl",
    "en": "en",
    "de": "german",
    "fr": "french",
    "es": "es",
    "ru": "ru",
}


def _primary_paddle_lang(languages: list[str]) -> str:
    # PaddleOCR accepts a single language per detector instance; pick the first.
    return _PADDLE_LANG.get(languages[0], "en")


def _ocr_one(
    image_arr: np.ndarray,
    page_number: int,
    width: float,
    height: float,
    lang: str,
    use_gpu: bool,
) -> OcrPage:
    from paddleocr import PaddleOCR  # local import to keep process model clean

    ocr = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=use_gpu, show_log=False)
    raw = ocr.ocr(image_arr, cls=True)
    words: list[Word] = []
    if raw and raw[0]:
        for box, (text, conf) in raw[0]:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            words.append(
                Word(
                    text=text,
                    bbox=(float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))),
                    confidence=float(conf),
                )
            )
    return OcrPage(page_number=page_number, width=width, height=height, words=words)


class PaddleEngine(OcrEngine):
    name = "paddle"

    def run(
        self,
        pdf_path: Path,
        opts: EngineOptions,
        work_dir: Path,
        progress: Callable[..., None],
    ) -> OcrResult:
        work_dir.mkdir(parents=True, exist_ok=True)
        lang = _primary_paddle_lang(opts.languages)
        pil_pages = convert_from_path(str(pdf_path), dpi=300)

        prepared: list[tuple[int, np.ndarray, float, float]] = []
        for idx, pil in enumerate(pil_pages, start=1):
            pil = preprocess_image(pil, deskew=opts.deskew, denoise=opts.denoise)
            prepared.append((idx, np.array(pil), float(pil.width), float(pil.height)))

        total = len(prepared)
        done = 0
        pages: dict[int, OcrPage] = {}
        progress(pages_done=0, active_workers=opts.workers)

        if opts.use_cuda:
            workers = min(opts.workers, 2)
            executor: ThreadPoolExecutor | ProcessPoolExecutor = ThreadPoolExecutor(
                max_workers=workers
            )
        else:
            workers = max(1, opts.workers)
            executor = ProcessPoolExecutor(max_workers=workers)

        try:
            futures = [
                executor.submit(_ocr_one, arr, num, w, h, lang, opts.use_cuda)
                for (num, arr, w, h) in prepared
            ]
            for fut in as_completed(futures):
                page = fut.result()
                pages[page.page_number] = page
                done += 1
                progress(pages_done=done, active_workers=workers)
        finally:
            executor.shutdown(wait=True)

        ordered = [pages[i] for i in sorted(pages.keys())]
        progress(pages_done=total, active_workers=0)
        return OcrResult(
            pages=ordered,
            engine=self.name,
            languages=list(opts.languages),
            raw_searchable_pdf=None,
        )
```

- [ ] **Step 4: Run test, verify PASS (or skip if paddleocr missing)**

```bash
cd backend && uv run pytest tests/test_paddle_engine.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/ocr/paddle_engine.py backend/tests/test_paddle_engine.py
git commit -m "feat(backend): PaddleOCR engine (CPU pool + CUDA threadpool)"
```

---

## Task 12: TXT formatter

**Files:**
- Create: `backend/app/formats/__init__.py`
- Create: `backend/app/formats/text.py`
- Test: `backend/tests/test_format_text.py`

- [ ] **Step 1: Create `backend/app/formats/__init__.py`** (will fill registry later)

```python
```

- [ ] **Step 2: Write the failing test**

```python
from pathlib import Path

from app.formats.text import write_txt
from app.ocr.base import OcrPage, OcrResult, Word


def _result() -> OcrResult:
    pages = [
        OcrPage(
            page_number=1,
            width=100,
            height=100,
            words=[
                Word("Hello", (0, 0, 10, 5), 0.9),
                Word("world", (12, 0, 22, 5), 0.9),
            ],
        ),
        OcrPage(
            page_number=2,
            width=100,
            height=100,
            words=[Word("Page2", (0, 0, 10, 5), 0.9)],
        ),
    ]
    return OcrResult(pages=pages, engine="x", languages=["en"])


def test_writes_text(tmp_path: Path):
    out = write_txt(_result(), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Hello world" in text
    assert "Page2" in text
    assert "\f" in text or "\n\n" in text  # page separator
```

- [ ] **Step 3: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_format_text.py -v
```

- [ ] **Step 4: Write `backend/app/formats/text.py`**

```python
from __future__ import annotations

from pathlib import Path

from app.ocr.base import OcrPage, OcrResult


def _page_text(page: OcrPage) -> str:
    # Group words into lines by y-mid proximity; words sorted by x.
    if not page.words:
        return ""
    sorted_words = sorted(page.words, key=lambda w: ((w.bbox[1] + w.bbox[3]) / 2, w.bbox[0]))
    line_tol = max(8.0, page.height * 0.012)
    lines: list[list] = [[sorted_words[0]]]
    for w in sorted_words[1:]:
        y_mid = (w.bbox[1] + w.bbox[3]) / 2
        prev_mid = (lines[-1][-1].bbox[1] + lines[-1][-1].bbox[3]) / 2
        if abs(y_mid - prev_mid) <= line_tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return "\n".join(" ".join(w.text for w in sorted(line, key=lambda x: x.bbox[0])) for line in lines)


def write_txt(result: OcrResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "output.txt"
    parts = [f"--- Page {page.page_number} ---\n{_page_text(page)}" for page in result.pages]
    out.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return out
```

- [ ] **Step 5: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_format_text.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/formats backend/tests/test_format_text.py
git commit -m "feat(backend): TXT formatter"
```

---

## Task 13: Markdown formatter

**Files:**
- Create: `backend/app/formats/markdown.py`
- Test: `backend/tests/test_format_markdown.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from app.formats.markdown import write_markdown
from app.ocr.base import OcrPage, OcrResult, Word


def test_pages_separated_by_hr(tmp_path: Path):
    result = OcrResult(
        pages=[
            OcrPage(1, 100, 100, [Word("Alpha", (0, 0, 10, 5), 0.9)]),
            OcrPage(2, 100, 100, [Word("Beta", (0, 0, 10, 5), 0.9)]),
        ],
        engine="x",
        languages=["en"],
    )
    out = write_markdown(result, tmp_path)
    md = out.read_text(encoding="utf-8")
    assert "Alpha" in md and "Beta" in md
    assert "\n---\n" in md
    assert "## Page 1" in md and "## Page 2" in md
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_format_markdown.py -v
```

- [ ] **Step 3: Write `backend/app/formats/markdown.py`**

```python
from __future__ import annotations

from pathlib import Path

from app.formats.text import _page_text
from app.ocr.base import OcrResult


def write_markdown(result: OcrResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "output.md"
    chunks: list[str] = []
    for i, page in enumerate(result.pages):
        if i > 0:
            chunks.append("\n---\n")
        chunks.append(f"## Page {page.page_number}\n\n{_page_text(page)}\n")
    out.write_text("\n".join(chunks), encoding="utf-8")
    return out
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_format_markdown.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/formats/markdown.py backend/tests/test_format_markdown.py
git commit -m "feat(backend): Markdown formatter"
```

---

## Task 14: DOCX formatter

**Files:**
- Create: `backend/app/formats/docx.py`
- Test: `backend/tests/test_format_docx.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from docx import Document

from app.formats.docx import write_docx
from app.ocr.base import OcrPage, OcrResult, Word


def test_docx_contains_text(tmp_path: Path):
    result = OcrResult(
        pages=[
            OcrPage(1, 100, 100, [Word("Hello", (0, 0, 10, 5), 0.9)]),
            OcrPage(2, 100, 100, [Word("World", (0, 0, 10, 5), 0.9)]),
        ],
        engine="x",
        languages=["en"],
    )
    out = write_docx(result, tmp_path)
    doc = Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Hello" in text and "World" in text
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_format_docx.py -v
```

- [ ] **Step 3: Write `backend/app/formats/docx.py`**

```python
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_BREAK

from app.formats.text import _page_text
from app.ocr.base import OcrResult


def write_docx(result: OcrResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "output.docx"
    doc = Document()
    for i, page in enumerate(result.pages):
        if i > 0:
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        doc.add_heading(f"Page {page.page_number}", level=2)
        for line in _page_text(page).splitlines():
            if line.strip():
                doc.add_paragraph(line)
    doc.save(str(out))
    return out
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_format_docx.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/formats/docx.py backend/tests/test_format_docx.py
git commit -m "feat(backend): DOCX formatter"
```

---

## Task 15: Word-positions JSON formatter

**Files:**
- Create: `backend/app/formats/word_positions.py`
- Test: `backend/tests/test_format_json.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

from app.formats.word_positions import write_word_positions_json
from app.ocr.base import OcrPage, OcrResult, Word


def test_json_structure(tmp_path: Path):
    result = OcrResult(
        pages=[
            OcrPage(1, 595.0, 842.0, [Word("Cześć", (10, 20, 50, 35), 0.87)]),
        ],
        engine="paddle",
        languages=["pl"],
    )
    out = write_word_positions_json(result, tmp_path)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["engine"] == "paddle"
    assert data["languages"] == ["pl"]
    assert len(data["pages"]) == 1
    page = data["pages"][0]
    assert page["page_number"] == 1
    assert page["width"] == 595.0
    assert page["words"][0]["text"] == "Cześć"
    assert page["words"][0]["bbox"] == [10.0, 20.0, 50.0, 35.0]
    assert page["words"][0]["confidence"] == 0.87
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_format_json.py -v
```

- [ ] **Step 3: Write `backend/app/formats/word_positions.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from app.ocr.base import OcrResult


def write_word_positions_json(result: OcrResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "output.json"
    data = {
        "engine": result.engine,
        "languages": result.languages,
        "pages": [
            {
                "page_number": p.page_number,
                "width": p.width,
                "height": p.height,
                "words": [
                    {"text": w.text, "bbox": list(w.bbox), "confidence": w.confidence}
                    for w in p.words
                ],
            }
            for p in result.pages
        ],
    }
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_format_json.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/formats/word_positions.py backend/tests/test_format_json.py
git commit -m "feat(backend): JSON word-positions formatter"
```

---

## Task 16: Searchable-PDF formatter

**Files:**
- Create: `backend/app/formats/searchable_pdf.py`
- Test: `backend/tests/test_format_pdf.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pdfplumber

from app.formats.searchable_pdf import write_searchable_pdf
from app.ocr.base import OcrPage, OcrResult, Word


def test_passthrough_when_engine_provided(tmp_path: Path, text_pdf: Path):
    # Pretend OCRmyPDF gave us a searchable PDF already
    result = OcrResult(
        pages=[OcrPage(1, 595, 842, [])],
        engine="ocrmypdf",
        languages=["en"],
        raw_searchable_pdf=text_pdf,
    )
    out = write_searchable_pdf(result, tmp_path, original_pdf=text_pdf)
    assert out.exists()
    # Should be a copy/reference, not the original path
    assert out.parent == tmp_path


def test_overlay_for_paddle(tmp_path: Path, text_pdf: Path):
    result = OcrResult(
        pages=[OcrPage(1, 595.0, 842.0, [Word("Hello", (72.0, 800.0, 200.0, 820.0), 0.95)])],
        engine="paddle",
        languages=["en"],
        raw_searchable_pdf=None,
    )
    out = write_searchable_pdf(result, tmp_path, original_pdf=text_pdf)
    assert out.exists()
    with pdfplumber.open(str(out)) as pdf:
        extracted = pdf.pages[0].extract_text() or ""
    assert "Hello" in extracted
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_format_pdf.py -v
```

- [ ] **Step 3: Write `backend/app/formats/searchable_pdf.py`**

```python
from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

import pikepdf
from pdf2image import convert_from_path
from reportlab.pdfgen import canvas

from app.ocr.base import OcrResult


def write_searchable_pdf(
    result: OcrResult, out_dir: Path, *, original_pdf: Path
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "output.pdf"
    if result.raw_searchable_pdf is not None:
        shutil.copyfile(result.raw_searchable_pdf, out)
        return out
    _build_overlay(result, original_pdf, out)
    return out


def _build_overlay(result: OcrResult, original_pdf: Path, out: Path) -> None:
    # Render original pages to images, draw invisible text at the OCR boxes on top.
    images = convert_from_path(str(original_pdf), dpi=300)
    base_pdf = pikepdf.Pdf.open(str(original_pdf))
    overlay_buf = BytesIO()
    # Use the original page sizes (points) from base_pdf
    sizes = [
        (float(p.mediabox[2] - p.mediabox[0]), float(p.mediabox[3] - p.mediabox[1]))
        for p in base_pdf.pages
    ]

    c = canvas.Canvas(overlay_buf)
    for page_idx, page in enumerate(result.pages):
        if page_idx >= len(sizes):
            break
        page_w, page_h = sizes[page_idx]
        img = images[page_idx]
        sx = page_w / img.width
        sy = page_h / img.height
        c.setPageSize((page_w, page_h))
        # Invisible text (render mode 3)
        c.saveState()
        c.setFillColorRGB(0, 0, 0)
        text = c.beginText()
        for w in page.words:
            x0, y0, x1, y1 = w.bbox
            # Convert image-space box (top-left origin) to PDF space (bottom-left origin).
            pdf_x = x0 * sx
            pdf_y = page_h - (y1 * sy)
            font_size = max(1.0, (y1 - y0) * sy)
            c.setFont("Helvetica", font_size)
            text = c.beginText(pdf_x, pdf_y)
            text.setTextRenderMode(3)  # invisible
            text.textLine(w.text)
            c.drawText(text)
        c.restoreState()
        c.showPage()
    c.save()

    overlay_buf.seek(0)
    overlay = pikepdf.Pdf.open(overlay_buf)
    for base_page, overlay_page in zip(base_pdf.pages, overlay.pages):
        base_page.add_overlay(overlay_page)
    base_pdf.save(str(out))
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_format_pdf.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/formats/searchable_pdf.py backend/tests/test_format_pdf.py
git commit -m "feat(backend): searchable PDF formatter (passthrough + overlay)"
```

---

## Task 17: Formatters registry

**Files:**
- Modify: `backend/app/formats/__init__.py`
- Test: `backend/tests/test_formats_registry.py`

- [ ] **Step 1: Write the failing test**

```python
from app.formats import FORMATTERS
from app.jobs.models import OutputFormat


def test_registry_covers_all_formats():
    assert set(FORMATTERS.keys()) == set(OutputFormat)
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_formats_registry.py -v
```

- [ ] **Step 3: Write `backend/app/formats/__init__.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.formats.docx import write_docx
from app.formats.markdown import write_markdown
from app.formats.searchable_pdf import write_searchable_pdf
from app.formats.text import write_txt
from app.formats.word_positions import write_word_positions_json
from app.jobs.models import OutputFormat
from app.ocr.base import OcrResult


def _txt(result: OcrResult, out_dir: Path, original_pdf: Path) -> Path:
    return write_txt(result, out_dir)


def _md(result: OcrResult, out_dir: Path, original_pdf: Path) -> Path:
    return write_markdown(result, out_dir)


def _docx(result: OcrResult, out_dir: Path, original_pdf: Path) -> Path:
    return write_docx(result, out_dir)


def _json(result: OcrResult, out_dir: Path, original_pdf: Path) -> Path:
    return write_word_positions_json(result, out_dir)


def _pdf(result: OcrResult, out_dir: Path, original_pdf: Path) -> Path:
    return write_searchable_pdf(result, out_dir, original_pdf=original_pdf)


FORMATTERS: dict[OutputFormat, Callable[[OcrResult, Path, Path], Path]] = {
    OutputFormat.txt: _txt,
    OutputFormat.md: _md,
    OutputFormat.docx: _docx,
    OutputFormat.json: _json,
    OutputFormat.pdf: _pdf,
}
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_formats_registry.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/formats/__init__.py backend/tests/test_formats_registry.py
git commit -m "feat(backend): formatter registry"
```

---

## Task 18: Runner orchestration

**Files:**
- Create: `backend/app/pipeline/runner.py`
- Test: `backend/tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from app.jobs.models import (
    Device,
    Engine,
    JobRequest,
    JobStage,
    JobStatus,
    Language,
    OutputFormat,
    Preprocess,
)
from app.jobs.store import JobStore
from app.pipeline.runner import run_job

pytestmark = pytest.mark.skipif(
    not __import__("shutil").which("tesseract"), reason="tesseract not installed"
)


def test_runner_produces_outputs(tmp_path: Path, text_pdf: Path):
    store = JobStore(ttl_seconds=600)
    req = JobRequest(
        file_id="t",
        engine=Engine.ocrmypdf,
        languages=[Language.en],
        page_range=(1, 1),
        preprocess=Preprocess(),
        formats=[OutputFormat.txt, OutputFormat.pdf, OutputFormat.json],
        workers=1,
        device=Device.cpu,
    )
    work_dir = tmp_path / "job"
    work_dir.mkdir()
    # Pretend file_id resolved to text_pdf
    state = store.create(work_dir=work_dir, total_pages=1, request=req)
    run_job(store=store, job_id=state.job_id, input_pdf=text_pdf)

    final = store.get(state.job_id)
    assert final.status == JobStatus.done
    assert final.stage == JobStage.finished
    produced = {o.format for o in final.outputs}
    assert produced == {OutputFormat.txt, OutputFormat.pdf, OutputFormat.json}
    for out in final.outputs:
        assert out.path.exists()
        assert out.size_bytes > 0
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_runner.py -v
```

- [ ] **Step 3: Write `backend/app/pipeline/runner.py`**

```python
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
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_runner.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/runner.py backend/tests/test_runner.py
git commit -m "feat(backend): job runner orchestration"
```

---

## Task 19: Upload API

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/upload.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_upload.py`

- [ ] **Step 1: Create `backend/app/api/__init__.py`**

```python
```

- [ ] **Step 2: Write the failing test**

```python
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_upload_returns_metadata(text_pdf: Path):
    client = TestClient(app)
    with text_pdf.open("rb") as f:
        r = client.post("/api/upload", files={"file": ("doc.pdf", f, "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["page_count"] == 1
    assert body["size_bytes"] > 0
    assert len(body["file_id"]) == 32


def test_upload_rejects_non_pdf(tmp_path: Path):
    junk = tmp_path / "x.txt"
    junk.write_text("not a pdf")
    client = TestClient(app)
    with junk.open("rb") as f:
        r = client.post("/api/upload", files={"file": ("x.txt", f, "text/plain")})
    assert r.status_code == 400
```

- [ ] **Step 3: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_api_upload.py -v
```

- [ ] **Step 4: Write `backend/app/api/upload.py`**

```python
from __future__ import annotations

import uuid
from pathlib import Path

import pypdf
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings

router = APIRouter(prefix="/api", tags=["upload"])


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
        reader = pypdf.PdfReader(str(target))
        page_count = len(reader.pages)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not open PDF: {exc}") from exc

    if page_count == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="PDF has no pages")
    if page_count > settings.max_pages:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail=f"PDF has {page_count} pages, max is {settings.max_pages}",
        )

    return {"file_id": file_id, "page_count": page_count, "size_bytes": size}


def upload_path(file_id: str) -> Path:
    return get_settings().temp_dir / "uploads" / f"{file_id}.pdf"
```

- [ ] **Step 5: Modify `backend/app/main.py` — register the router**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import upload as upload_api

app = FastAPI(title="OCR PDF API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3101", "http://localhost:3101"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_api.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_api_upload.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/api backend/app/main.py backend/tests/test_api_upload.py
git commit -m "feat(backend): upload endpoint"
```

---

## Task 20: System info API

**Files:**
- Create: `backend/app/api/system.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_system.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_system_info():
    client = TestClient(app)
    r = client.get("/api/system/info")
    assert r.status_code == 200
    body = r.json()
    assert body["cpu"]["count"] >= 1
    assert "ram" in body and "gpu" in body
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_api_system.py -v
```

- [ ] **Step 3: Write `backend/app/api/system.py`**

```python
from fastapi import APIRouter

from app.system_info import get_system_info

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info")
def info() -> dict:
    return get_system_info()
```

- [ ] **Step 4: Modify `backend/app/main.py` — add the import and `include_router`**

Insert `from app.api import system as system_api` next to the other imports, and add `app.include_router(system_api.router)` next to the existing `include_router` call.

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import system as system_api
from app.api import upload as upload_api

app = FastAPI(title="OCR PDF API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3101", "http://localhost:3101"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_api.router)
app.include_router(system_api.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_api_system.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/system.py backend/app/main.py backend/tests/test_api_system.py
git commit -m "feat(backend): system info endpoint"
```

---

## Task 21: Jobs API + background execution

**Files:**
- Create: `backend/app/jobs/runtime.py` (process executor singleton)
- Create: `backend/app/api/jobs.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_jobs.py`

- [ ] **Step 1: Write `backend/app/jobs/runtime.py`**

```python
from __future__ import annotations

import threading

from app.config import get_settings
from app.jobs.store import JobStore

_lock = threading.Lock()
_store: JobStore | None = None


def get_store() -> JobStore:
    global _store
    with _lock:
        if _store is None:
            _store = JobStore(ttl_seconds=get_settings().job_ttl_seconds)
    return _store
```

- [ ] **Step 2: Write the failing test**

```python
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    not __import__("shutil").which("tesseract"), reason="tesseract not installed"
)


def _upload(client: TestClient, pdf: Path) -> str:
    with pdf.open("rb") as f:
        r = client.post("/api/upload", files={"file": ("d.pdf", f, "application/pdf")})
    assert r.status_code == 200
    return r.json()["file_id"]


def test_full_job_flow(text_pdf: Path):
    client = TestClient(app)
    file_id = _upload(client, text_pdf)

    r = client.post(
        "/api/jobs",
        json={
            "file_id": file_id,
            "engine": "ocrmypdf",
            "languages": ["en"],
            "page_range": [1, 1],
            "preprocess": {"deskew": False, "denoise": False},
            "formats": ["txt", "pdf"],
            "workers": 1,
            "device": "cpu",
        },
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    deadline = time.time() + 120
    while time.time() < deadline:
        rs = client.get(f"/api/jobs/{job_id}")
        assert rs.status_code == 200
        body = rs.json()
        if body["status"] == "done":
            break
        if body["status"] == "failed":
            raise AssertionError(body)
        time.sleep(0.5)
    else:
        raise AssertionError("job did not finish in time")

    formats = {o["format"] for o in body["outputs"]}
    assert formats == {"txt", "pdf"}


def test_job_status_missing():
    client = TestClient(app)
    r = client.get("/api/jobs/nope")
    assert r.status_code == 404
```

- [ ] **Step 3: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_api_jobs.py -v
```

- [ ] **Step 4: Write `backend/app/api/jobs.py`**

```python
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
```

- [ ] **Step 5: Modify `backend/app/main.py` — register the jobs router**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import jobs as jobs_api
from app.api import system as system_api
from app.api import upload as upload_api

app = FastAPI(title="OCR PDF API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3101", "http://localhost:3101"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_api.router)
app.include_router(system_api.router)
app.include_router(jobs_api.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_api_jobs.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/jobs/runtime.py backend/app/api/jobs.py backend/app/main.py backend/tests/test_api_jobs.py
git commit -m "feat(backend): jobs API (create, status) with background runner"
```

---

## Task 22: Download API

**Files:**
- Create: `backend/app/api/download.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_download.py`

- [ ] **Step 1: Write the failing test**

```python
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.skipif(
    not __import__("shutil").which("tesseract"), reason="tesseract not installed"
)


def test_download_returns_file(text_pdf: Path):
    client = TestClient(app)
    with text_pdf.open("rb") as f:
        upl = client.post("/api/upload", files={"file": ("d.pdf", f, "application/pdf")}).json()
    job = client.post(
        "/api/jobs",
        json={
            "file_id": upl["file_id"],
            "engine": "ocrmypdf",
            "languages": ["en"],
            "page_range": [1, 1],
            "preprocess": {"deskew": False, "denoise": False},
            "formats": ["txt"],
            "workers": 1,
            "device": "cpu",
        },
    ).json()
    job_id = job["job_id"]
    for _ in range(240):
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] == "done":
            break
        time.sleep(0.5)
    r = client.get(f"/api/jobs/{job_id}/download/txt")
    assert r.status_code == 200
    assert "hello" in r.text.lower()


def test_download_unknown_format(text_pdf: Path):
    client = TestClient(app)
    r = client.get("/api/jobs/nope/download/txt")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/test_api_download.py -v
```

- [ ] **Step 3: Write `backend/app/api/download.py`**

```python
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
```

- [ ] **Step 4: Modify `backend/app/main.py` — register the download router**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import download as download_api
from app.api import jobs as jobs_api
from app.api import system as system_api
from app.api import upload as upload_api

app = FastAPI(title="OCR PDF API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3101", "http://localhost:3101"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_api.router)
app.include_router(system_api.router)
app.include_router(jobs_api.router)
app.include_router(download_api.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_api_download.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/download.py backend/app/main.py backend/tests/test_api_download.py
git commit -m "feat(backend): download endpoint"
```

---

## Task 23: TTL sweeper lifespan + logging

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_lifespan.py`

- [ ] **Step 1: Write the failing test**

```python
import asyncio

from fastapi.testclient import TestClient

from app.main import app


def test_app_starts_with_sweeper():
    with TestClient(app) as client:
        # if lifespan crashes, this with-block raises
        assert client.get("/api/health").status_code == 200
```

- [ ] **Step 2: Run test, verify it fails or trivially passes (no lifespan yet)**

```bash
cd backend && uv run pytest tests/test_lifespan.py -v
```

(May trivially pass even without lifespan; the real verification comes from running the app.)

- [ ] **Step 3: Modify `backend/app/main.py` — add lifespan with sweeper task**

```python
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import download as download_api
from app.api import jobs as jobs_api
from app.api import system as system_api
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
app.include_router(system_api.router)
app.include_router(jobs_api.router)
app.include_router(download_api.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd backend && uv run pytest tests/test_lifespan.py -v
```

- [ ] **Step 5: Run full backend suite**

```bash
cd backend && uv run pytest -q
```

Expected: all PASS (engine tests skip if their deps are missing).

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_lifespan.py
git commit -m "feat(backend): lifespan with TTL sweeper and logging"
```

---

## Task 24: Frontend bootstrap (Next.js 15 + Tailwind 4 + shadcn)

**Files:**
- Create: everything under `frontend/`

- [ ] **Step 1: Create Next.js app**

```bash
cd frontend && pnpm dlx create-next-app@15 . --typescript --tailwind --eslint --app --src-dir=false --import-alias '@/*' --use-pnpm
```

Accept defaults for any prompts that remain.

- [ ] **Step 2: Initialize shadcn**

```bash
cd frontend && pnpm dlx shadcn@latest init -d
```

- [ ] **Step 3: Add shadcn components used by the UI**

```bash
cd frontend && pnpm dlx shadcn@latest add button card checkbox dropdown-menu label popover progress radio-group select separator slider sonner switch tooltip
```

- [ ] **Step 4: Install runtime deps**

```bash
cd frontend && pnpm add framer-motion react-dropzone lucide-react
```

- [ ] **Step 5: Install dev/test deps**

```bash
cd frontend && pnpm add -D vitest @vitest/ui jsdom @testing-library/react @testing-library/jest-dom playwright @playwright/test
cd frontend && pnpm exec playwright install chromium
```

- [ ] **Step 6: Add npm scripts**

Edit `frontend/package.json` so the `scripts` block contains:

```json
{
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "next lint",
  "test": "vitest run",
  "test:watch": "vitest",
  "e2e": "playwright test"
}
```

- [ ] **Step 7: Add vitest config — `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
```

- [ ] **Step 8: Add vitest setup — `frontend/tests/setup.ts`**

```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 9: Add Playwright config — `frontend/playwright.config.ts`**

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:3101" },
  reporter: "list",
});
```

- [ ] **Step 10: Smoke test**

```bash
cd frontend && pnpm test
```

Expected: no tests yet → "No test files found" is acceptable (exit code 1). Configure to PASS by adding a trivial test file before commit, or proceed — the next task adds real tests.

- [ ] **Step 11: Commit**

```bash
git add frontend
git commit -m "chore(frontend): bootstrap Next.js + Tailwind + shadcn + vitest + playwright"
```

---

## Task 25: Frontend types (`lib/types.ts`)

**Files:**
- Create: `frontend/lib/types.ts`

- [ ] **Step 1: Write `frontend/lib/types.ts`**

```typescript
export type Engine = "ocrmypdf" | "paddle";
export type Device = "cpu" | "cuda";
export type Language = "pl" | "en" | "de" | "fr" | "es" | "ru";
export type OutputFormat = "pdf" | "txt" | "md" | "docx" | "json";
export type JobStatus = "pending" | "running" | "done" | "failed";
export type JobStage =
  | "queued"
  | "downloading_models"
  | "preprocessing"
  | "ocr"
  | "formatting"
  | "finished";

export interface SystemInfo {
  cpu: { count: number; model: string };
  ram: { total_gb: number; available_gb: number };
  gpu: {
    cuda_available: boolean;
    devices: Array<{ id: number; name: string; vram_gb: number; driver: string }>;
    paddle_gpu_installed: boolean;
  };
}

export interface UploadResponse {
  file_id: string;
  page_count: number;
  size_bytes: number;
}

export interface Preprocess {
  deskew: boolean;
  denoise: boolean;
}

export interface JobRequest {
  file_id: string;
  engine: Engine;
  languages: Language[];
  page_range: [number, number];
  preprocess: Preprocess;
  formats: OutputFormat[];
  workers: number;
  device: Device;
}

export interface JobOutput {
  format: OutputFormat;
  url: string;
  size_bytes: number;
}

export interface JobState {
  job_id: string;
  status: JobStatus;
  stage: JobStage;
  progress_pct: number;
  pages_done: number;
  total_pages: number;
  active_workers: number;
  warnings: string[];
  error: { message: string; details: string | null } | null;
  outputs: JobOutput[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/types.ts
git commit -m "feat(frontend): API types"
```

---

## Task 26: Frontend API client (`lib/api.ts`)

**Files:**
- Create: `frontend/lib/api.ts`
- Test: `frontend/tests/api.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { uploadPdf, createJob, getJob, downloadUrl, getSystemInfo } from "@/lib/api";

const originalFetch = global.fetch;

describe("api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    global.fetch = originalFetch;
  });

  it("uploads a PDF", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ file_id: "abc", page_count: 3, size_bytes: 100 }),
    });
    const file = new File([new Uint8Array([1, 2, 3])], "x.pdf", { type: "application/pdf" });
    const r = await uploadPdf(file);
    expect(r.page_count).toBe(3);
    expect((global.fetch as any).mock.calls[0][0]).toMatch(/\/api\/upload$/);
  });

  it("creates a job", async () => {
    (global.fetch as any).mockResolvedValue({ ok: true, json: async () => ({ job_id: "j" }) });
    const r = await createJob({
      file_id: "f",
      engine: "ocrmypdf",
      languages: ["pl"],
      page_range: [1, 2],
      preprocess: { deskew: true, denoise: false },
      formats: ["txt"],
      workers: 2,
      device: "cpu",
    });
    expect(r.job_id).toBe("j");
  });

  it("gets job status", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        job_id: "j",
        status: "running",
        stage: "ocr",
        progress_pct: 50,
        pages_done: 1,
        total_pages: 2,
        active_workers: 1,
        warnings: [],
        error: null,
        outputs: [],
      }),
    });
    const r = await getJob("j");
    expect(r.status).toBe("running");
  });

  it("builds download URL", () => {
    expect(downloadUrl("j", "pdf")).toMatch(/\/api\/jobs\/j\/download\/pdf$/);
  });

  it("fetches system info", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        cpu: { count: 8, model: "X" },
        ram: { total_gb: 16, available_gb: 8 },
        gpu: { cuda_available: false, devices: [], paddle_gpu_installed: false },
      }),
    });
    const r = await getSystemInfo();
    expect(r.cpu.count).toBe(8);
  });

  it("throws on non-ok response", async () => {
    (global.fetch as any).mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: "bad" }),
    });
    await expect(getJob("x")).rejects.toThrow(/bad/);
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd frontend && pnpm test
```

- [ ] **Step 3: Write `frontend/lib/api.ts`**

```typescript
import type {
  JobRequest,
  JobState,
  OutputFormat,
  SystemInfo,
  UploadResponse,
} from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8114";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, init);
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      const body = await r.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await r.json()) as T;
}

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/api/upload", { method: "POST", body: form });
}

export async function createJob(req: JobRequest): Promise<{ job_id: string }> {
  return request("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function getJob(id: string): Promise<JobState> {
  return request<JobState>(`/api/jobs/${id}`);
}

export function downloadUrl(id: string, fmt: OutputFormat): string {
  return `${BASE}/api/jobs/${id}/download/${fmt}`;
}

export async function getSystemInfo(): Promise<SystemInfo> {
  return request<SystemInfo>("/api/system/info");
}
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd frontend && pnpm test
```

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/tests/api.test.ts
git commit -m "feat(frontend): API client with unit tests"
```

---

## Task 27: Format matrix (`lib/format-matrix.ts`)

**Files:**
- Create: `frontend/lib/format-matrix.ts`
- Test: `frontend/tests/format-matrix.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
import { describe, expect, it } from "vitest";
import { formatQuality, formatWarning } from "@/lib/format-matrix";

describe("format-matrix", () => {
  it("ranks JSON higher for paddle than ocrmypdf", () => {
    expect(formatQuality("paddle", "json")).toBe("native");
    expect(formatQuality("ocrmypdf", "json")).toBe("derived");
  });

  it("ranks searchable PDF native for ocrmypdf", () => {
    expect(formatQuality("ocrmypdf", "pdf")).toBe("native");
    expect(formatQuality("paddle", "pdf")).toBe("derived");
  });

  it("emits a warning string for derived formats", () => {
    expect(formatWarning("ocrmypdf", "json")).toMatch(/extracted/i);
    expect(formatWarning("paddle", "json")).toBeNull();
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd frontend && pnpm test
```

- [ ] **Step 3: Write `frontend/lib/format-matrix.ts`**

```typescript
import type { Engine, OutputFormat } from "@/lib/types";

type Quality = "native" | "derived";

const MATRIX: Record<Engine, Record<OutputFormat, Quality>> = {
  ocrmypdf: { pdf: "native", txt: "native", md: "derived", docx: "derived", json: "derived" },
  paddle:   { pdf: "derived", txt: "derived", md: "derived", docx: "derived", json: "native" },
};

const WARNINGS: Partial<Record<Engine, Partial<Record<OutputFormat, string>>>> = {
  ocrmypdf: {
    json: "JSON positions for OCRmyPDF are extracted from the text layer (less precise than Paddle's native boxes).",
    md: "Markdown structure is approximate; no heading/table detection.",
    docx: "DOCX layout is paragraph-only; no formatting recovery.",
  },
  paddle: {
    pdf: "Searchable PDF for PaddleOCR is built by overlaying invisible text on the original pages.",
    md: "Markdown structure is approximate; no heading/table detection.",
    docx: "DOCX layout is paragraph-only; no formatting recovery.",
  },
};

export function formatQuality(engine: Engine, fmt: OutputFormat): Quality {
  return MATRIX[engine][fmt];
}

export function formatWarning(engine: Engine, fmt: OutputFormat): string | null {
  return WARNINGS[engine]?.[fmt] ?? null;
}
```

- [ ] **Step 4: Run test, verify PASS**

```bash
cd frontend && pnpm test
```

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/format-matrix.ts frontend/tests/format-matrix.test.ts
git commit -m "feat(frontend): format quality matrix"
```

---

## Task 28: `useJobStatus` hook

**Files:**
- Create: `frontend/hooks/use-job-status.ts`

- [ ] **Step 1: Write `frontend/hooks/use-job-status.ts`**

```typescript
"use client";

import { useEffect, useRef, useState } from "react";
import { getJob } from "@/lib/api";
import type { JobState } from "@/lib/types";

export function useJobStatus(jobId: string | null, intervalMs = 1000) {
  const [state, setState] = useState<JobState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!jobId) return;
    setState(null);
    setError(null);
    const ac = new AbortController();
    abortRef.current = ac;
    let stopped = false;
    const tick = async () => {
      while (!stopped) {
        try {
          const next = await getJob(jobId);
          if (stopped) return;
          setState(next);
          if (next.status === "done" || next.status === "failed") return;
        } catch (e) {
          if (!stopped) setError((e as Error).message);
          return;
        }
        await new Promise((r) => setTimeout(r, intervalMs));
      }
    };
    void tick();
    return () => {
      stopped = true;
      ac.abort();
    };
  }, [jobId, intervalMs]);

  return { state, error, stop: () => abortRef.current?.abort() };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/hooks/use-job-status.ts
git commit -m "feat(frontend): useJobStatus polling hook"
```

---

## Task 29: Hardware chip component

**Files:**
- Create: `frontend/components/hardware-chip.tsx`

- [ ] **Step 1: Write `frontend/components/hardware-chip.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { Cpu, MemoryStick, Zap } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { getSystemInfo } from "@/lib/api";
import type { SystemInfo } from "@/lib/types";

export function HardwareChip() {
  const [info, setInfo] = useState<SystemInfo | null>(null);

  useEffect(() => {
    getSystemInfo().then(setInfo).catch(() => setInfo(null));
  }, []);

  if (!info) {
    return (
      <div className="text-xs text-muted-foreground px-2 py-1 rounded-full border">
        detecting hardware…
      </div>
    );
  }

  const cuda = info.gpu.cuda_available;
  const gpuLabel = info.gpu.devices[0]?.name ?? "no GPU";

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="text-xs px-3 py-1.5 rounded-full border flex items-center gap-3 hover:bg-accent transition-colors"
          aria-label="Hardware info"
        >
          <span className="flex items-center gap-1">
            <Cpu className="h-3.5 w-3.5" />
            {info.cpu.count}
          </span>
          <span className="flex items-center gap-1">
            <MemoryStick className="h-3.5 w-3.5" />
            {Math.round(info.ram.total_gb)} GB
          </span>
          <span className="flex items-center gap-1">
            <Zap className={`h-3.5 w-3.5 ${cuda ? "text-green-500" : "text-muted-foreground"}`} />
            {cuda ? gpuLabel : "CPU only"}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 text-sm space-y-2">
        <div>
          <div className="font-medium">CPU</div>
          <div className="text-muted-foreground">
            {info.cpu.count} cores · {info.cpu.model}
          </div>
        </div>
        <div>
          <div className="font-medium">RAM</div>
          <div className="text-muted-foreground">
            {info.ram.available_gb.toFixed(1)} GB free / {info.ram.total_gb.toFixed(1)} GB total
          </div>
        </div>
        <div>
          <div className="font-medium">GPU</div>
          {info.gpu.devices.length === 0 ? (
            <div className="text-muted-foreground">no GPU detected</div>
          ) : (
            <ul className="text-muted-foreground">
              {info.gpu.devices.map((d) => (
                <li key={d.id}>
                  {d.name} · {d.vram_gb} GB · driver {d.driver}
                </li>
              ))}
            </ul>
          )}
          <div className="text-muted-foreground">
            {info.gpu.paddle_gpu_installed
              ? "paddlepaddle-gpu installed"
              : "paddlepaddle-gpu not installed (CPU only)"}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/hardware-chip.tsx
git commit -m "feat(frontend): hardware chip with popover"
```

---

## Task 30: Dropzone component

**Files:**
- Create: `frontend/components/dropzone.tsx`

- [ ] **Step 1: Write `frontend/components/dropzone.tsx`**

```tsx
"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion } from "framer-motion";
import { FileText, Upload } from "lucide-react";
import { toast } from "sonner";
import { uploadPdf } from "@/lib/api";
import type { UploadResponse } from "@/lib/types";

interface Props {
  onUploaded: (resp: UploadResponse, file: File) => void;
  disabled?: boolean;
}

export function Dropzone({ onUploaded, disabled }: Props) {
  const [busy, setBusy] = useState(false);
  const [filename, setFilename] = useState<string | null>(null);

  const onDrop = useCallback(
    async (files: File[]) => {
      const file = files[0];
      if (!file) return;
      setBusy(true);
      setFilename(file.name);
      try {
        const resp = await uploadPdf(file);
        onUploaded(resp, file);
      } catch (e) {
        toast.error((e as Error).message);
        setFilename(null);
      } finally {
        setBusy(false);
      }
    },
    [onUploaded],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    multiple: false,
    disabled: disabled || busy,
  });

  return (
    <motion.div
      {...getRootProps()}
      initial={false}
      animate={{ scale: isDragActive ? 1.01 : 1 }}
      className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors
        ${isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"}
        ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
    >
      <input {...getInputProps()} aria-label="Choose PDF file" />
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        {filename ? (
          <>
            <FileText className="h-10 w-10 text-primary" />
            <div className="text-sm">{filename}</div>
            <div className="text-xs">{busy ? "Uploading…" : "Drop another to replace"}</div>
          </>
        ) : (
          <>
            <Upload className="h-10 w-10" />
            <div className="text-base">Drop your PDF here</div>
            <div className="text-xs">or click to browse</div>
          </>
        )}
      </div>
    </motion.div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/dropzone.tsx
git commit -m "feat(frontend): dropzone with upload"
```

---

## Task 31: Job options form

**Files:**
- Create: `frontend/components/job-options.tsx`

- [ ] **Step 1: Write `frontend/components/job-options.tsx`**

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { Cpu, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { formatWarning } from "@/lib/format-matrix";
import type {
  Device,
  Engine,
  JobRequest,
  Language,
  OutputFormat,
  SystemInfo,
} from "@/lib/types";

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "pl", label: "Polish" },
  { value: "en", label: "English" },
  { value: "de", label: "German" },
  { value: "fr", label: "French" },
  { value: "es", label: "Spanish" },
  { value: "ru", label: "Russian" },
];

const FORMATS: { value: OutputFormat; label: string }[] = [
  { value: "pdf", label: "Searchable PDF" },
  { value: "txt", label: "Plain text" },
  { value: "md", label: "Markdown" },
  { value: "docx", label: "DOCX" },
  { value: "json", label: "JSON (positions)" },
];

interface Props {
  fileId: string;
  pageCount: number;
  system: SystemInfo | null;
  defaultWorkers: number;
  onSubmit: (req: JobRequest) => void;
  submitting: boolean;
}

export function JobOptions({
  fileId,
  pageCount,
  system,
  defaultWorkers,
  onSubmit,
  submitting,
}: Props) {
  const [engine, setEngine] = useState<Engine>("ocrmypdf");
  const [languages, setLanguages] = useState<Language[]>(["pl", "en"]);
  const [range, setRange] = useState<[number, number]>([1, pageCount]);
  const [deskew, setDeskew] = useState(true);
  const [denoise, setDenoise] = useState(true);
  const [formats, setFormats] = useState<OutputFormat[]>(["pdf", "txt"]);
  const [workers, setWorkers] = useState<number>(defaultWorkers);
  const [device, setDevice] = useState<Device>("cpu");

  useEffect(() => {
    setRange([1, pageCount]);
  }, [pageCount]);

  const cudaAvailable = !!system?.gpu.cuda_available && engine === "paddle";

  useEffect(() => {
    if (!cudaAvailable && device === "cuda") setDevice("cpu");
  }, [cudaAvailable, device]);

  const workerOptions = useMemo(() => {
    const max = system?.cpu.count ?? defaultWorkers;
    const opts = [1, 2, 4, 8, 12, 16, 24, 32].filter((n) => n <= max);
    if (!opts.includes(max)) opts.push(max);
    return Array.from(new Set(opts)).sort((a, b) => a - b);
  }, [system, defaultWorkers]);

  const toggle = <T,>(arr: T[], v: T): T[] =>
    arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];

  const canSubmit =
    languages.length > 0 && formats.length > 0 && range[0] >= 1 && range[1] >= range[0];

  const handleSubmit = () => {
    onSubmit({
      file_id: fileId,
      engine,
      languages,
      page_range: range,
      preprocess: { deskew, denoise },
      formats,
      workers,
      device,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Options</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label>Engine</Label>
            <RadioGroup value={engine} onValueChange={(v) => setEngine(v as Engine)}>
              <div className="flex items-center gap-2">
                <RadioGroupItem id="eng-ocr" value="ocrmypdf" />
                <Label htmlFor="eng-ocr">OCRmyPDF (Tesseract)</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem id="eng-paddle" value="paddle" />
                <Label htmlFor="eng-paddle">PaddleOCR</Label>
              </div>
            </RadioGroup>
          </div>

          <div className="space-y-2">
            <Label>Languages</Label>
            <div className="grid grid-cols-3 gap-2">
              {LANGUAGES.map((l) => (
                <label key={l.value} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={languages.includes(l.value)}
                    onCheckedChange={() => setLanguages(toggle(languages, l.value))}
                  />
                  {l.label}
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <Label>
            Pages: {range[0]} – {range[1]} of {pageCount}
          </Label>
          <Slider
            min={1}
            max={pageCount}
            step={1}
            value={range}
            onValueChange={(v) => setRange([v[0], v[1]] as [number, number])}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label>Preprocessing</Label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={deskew} onCheckedChange={(v) => setDeskew(!!v)} />
              Deskew
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={denoise} onCheckedChange={(v) => setDenoise(!!v)} />
              Denoise
            </label>
          </div>

          <div className="space-y-2">
            <Label>Output formats</Label>
            <div className="grid grid-cols-2 gap-2">
              {FORMATS.map((f) => {
                const warn = formatWarning(engine, f.value);
                return (
                  <TooltipProvider key={f.value}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <label className="flex items-center gap-2 text-sm">
                          <Checkbox
                            checked={formats.includes(f.value)}
                            onCheckedChange={() => setFormats(toggle(formats, f.value))}
                          />
                          <span className={warn ? "underline decoration-dotted" : ""}>
                            {f.label}
                          </span>
                        </label>
                      </TooltipTrigger>
                      {warn && <TooltipContent>{warn}</TooltipContent>}
                    </Tooltip>
                  </TooltipProvider>
                );
              })}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Cpu className="h-4 w-4" /> Workers
            </Label>
            <Select
              value={String(workers)}
              onValueChange={(v) => setWorkers(parseInt(v, 10))}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {workerOptions.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n === defaultWorkers ? `Auto (${n})` : String(n)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {engine === "paddle" && (
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Zap className="h-4 w-4" /> Device
              </Label>
              <RadioGroup value={device} onValueChange={(v) => setDevice(v as Device)}>
                <div className="flex items-center gap-2">
                  <RadioGroupItem
                    id="dev-cuda"
                    value="cuda"
                    disabled={!cudaAvailable}
                  />
                  <Label htmlFor="dev-cuda" className={!cudaAvailable ? "opacity-50" : ""}>
                    CUDA{" "}
                    {system?.gpu.devices[0]
                      ? `(${system.gpu.devices[0].name})`
                      : "(unavailable)"}
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem id="dev-cpu" value="cpu" />
                  <Label htmlFor="dev-cpu">CPU</Label>
                </div>
              </RadioGroup>
            </div>
          )}
        </div>

        <div className="pt-2">
          <Button disabled={!canSubmit || submitting} onClick={handleSubmit} size="lg">
            {submitting ? "Starting…" : "Start OCR"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/job-options.tsx
git commit -m "feat(frontend): job options form"
```

---

## Task 32: Progress panel

**Files:**
- Create: `frontend/components/progress-panel.tsx`

- [ ] **Step 1: Write `frontend/components/progress-panel.tsx`**

```tsx
"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { JobState } from "@/lib/types";

const STAGE_LABEL: Record<JobState["stage"], string> = {
  queued: "Queued",
  downloading_models: "Downloading models",
  preprocessing: "Preparing pages",
  ocr: "Running OCR",
  formatting: "Building outputs",
  finished: "Finished",
};

export function ProgressPanel({ state }: { state: JobState }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Progress</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Progress value={state.progress_pct} />
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>{STAGE_LABEL[state.stage] ?? state.stage}</span>
          <span>
            {state.pages_done} / {state.total_pages} pages
            {state.active_workers > 0 && ` · ${state.active_workers} workers`}
          </span>
        </div>
        {state.warnings.length > 0 && (
          <ul className="text-xs text-amber-500 list-disc pl-4">
            {state.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/progress-panel.tsx
git commit -m "feat(frontend): progress panel"
```

---

## Task 33: Results panel

**Files:**
- Create: `frontend/components/results-panel.tsx`

- [ ] **Step 1: Write `frontend/components/results-panel.tsx`**

```tsx
"use client";

import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { downloadUrl } from "@/lib/api";
import type { JobState, OutputFormat } from "@/lib/types";

const LABELS: Record<OutputFormat, string> = {
  pdf: "PDF",
  txt: "TXT",
  md: "Markdown",
  docx: "DOCX",
  json: "JSON",
};

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ResultsPanel({ state }: { state: JobState }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Download</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-3">
        {state.outputs.map((o) => (
          <Button asChild key={o.format} variant="outline">
            <a href={downloadUrl(state.job_id, o.format)} download>
              <Download className="h-4 w-4 mr-2" />
              {LABELS[o.format]}
              <span className="ml-2 text-xs text-muted-foreground">{fmtSize(o.size_bytes)}</span>
            </a>
          </Button>
        ))}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/results-panel.tsx
git commit -m "feat(frontend): results panel"
```

---

## Task 34: Main page wiring

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Replace `frontend/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "OCR PDF",
  description: "Local OCR for PDF files",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-background text-foreground min-h-screen`}>
        {children}
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Replace `frontend/app/page.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { Dropzone } from "@/components/dropzone";
import { HardwareChip } from "@/components/hardware-chip";
import { JobOptions } from "@/components/job-options";
import { ProgressPanel } from "@/components/progress-panel";
import { ResultsPanel } from "@/components/results-panel";
import { useJobStatus } from "@/hooks/use-job-status";
import { createJob, getSystemInfo } from "@/lib/api";
import type { JobRequest, SystemInfo, UploadResponse } from "@/lib/types";

export default function Page() {
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { state, error } = useJobStatus(jobId);

  useEffect(() => {
    getSystemInfo().then(setSystem).catch(() => setSystem(null));
  }, []);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  useEffect(() => {
    if (state?.status === "failed" && state.error) toast.error(state.error.message);
  }, [state]);

  const handleSubmit = async (req: JobRequest) => {
    setSubmitting(true);
    try {
      const { job_id } = await createJob(req);
      setJobId(job_id);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleUploaded = (resp: UploadResponse) => {
    setUpload(resp);
    setJobId(null);
  };

  const defaultWorkers = system?.cpu.count ?? 1;

  return (
    <main className="max-w-3xl mx-auto p-6 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">OCR PDF</h1>
        <HardwareChip />
      </header>

      <Dropzone onUploaded={handleUploaded} disabled={state?.status === "running"} />

      <AnimatePresence>
        {upload && (
          <motion.div
            key="opts"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <JobOptions
              fileId={upload.file_id}
              pageCount={upload.page_count}
              system={system}
              defaultWorkers={defaultWorkers}
              onSubmit={handleSubmit}
              submitting={submitting || state?.status === "running"}
            />
          </motion.div>
        )}

        {state && state.status !== "done" && (
          <motion.div
            key="prog"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <ProgressPanel state={state} />
          </motion.div>
        )}

        {state?.status === "done" && (
          <motion.div
            key="res"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <ResultsPanel state={state} />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
```

- [ ] **Step 3: Ensure `frontend/app/globals.css` keeps the shadcn theme imports added by `shadcn init`.** No changes required unless you removed them. Verify the file still begins with the `@tailwind` or `@import "tailwindcss"` directive and any shadcn theme variables.

- [ ] **Step 4: Local smoke check**

In one terminal:

```bash
make backend
```

In another:

```bash
make frontend
```

Open `http://127.0.0.1:3101`, drop a small text PDF, pick OCRmyPDF + English + TXT, hit Start OCR, confirm the progress bar advances and the TXT downloads.

- [ ] **Step 5: Commit**

```bash
git add frontend/app
git commit -m "feat(frontend): wire main page (dropzone → options → progress → results)"
```

---

## Task 35: Playwright E2E smoke test

**Files:**
- Create: `frontend/e2e/upload-flow.spec.ts`
- Create: `frontend/e2e/fixtures/sample.pdf` (copied from backend fixture)

- [ ] **Step 1: Copy fixture for Playwright**

```bash
mkdir -p frontend/e2e/fixtures
cp backend/tests/fixtures/text_simple.pdf frontend/e2e/fixtures/sample.pdf
```

(Generate the fixture first by running `cd backend && uv run pytest tests/test_page_range.py -q` once; the conftest will create it.)

- [ ] **Step 2: Write `frontend/e2e/upload-flow.spec.ts`**

```typescript
import { expect, test } from "@playwright/test";
import path from "node:path";

test("upload → ocr → download", async ({ page }) => {
  await page.goto("/");
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(path.join(__dirname, "fixtures", "sample.pdf"));

  await expect(page.getByText("Options")).toBeVisible();
  // Ensure English is selected
  const en = page.locator('label', { hasText: "English" }).locator('button[role="checkbox"]');
  const enChecked = await en.getAttribute("aria-checked");
  if (enChecked !== "true") await en.click();

  await page.getByRole("button", { name: /start ocr/i }).click();
  await expect(page.getByText("Download")).toBeVisible({ timeout: 120_000 });

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: /TXT/ }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.txt$/);
});
```

- [ ] **Step 3: Run E2E (requires both servers running, tesseract installed)**

In separate terminals:

```bash
make backend
make frontend
# then
cd frontend && pnpm exec playwright test
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e
git commit -m "test(frontend): E2E upload → OCR → download flow"
```

---

## Task 36: Final polish — README run notes + sanity check

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Append a "Troubleshooting" section to `README.md`**

```markdown
## Troubleshooting

- **`tesseract: command not found`** — install Tesseract and the language data packs listed above.
- **`pdf2image` errors** — ensure `poppler` is installed (`pacman -S poppler`).
- **PaddleOCR downloads on first run** — models (~100 MB per language) are cached under `~/.paddleocr/`.
- **CUDA not detected** — verify `nvidia-smi` works, install with `cd backend && uv sync --extra gpu`, restart the backend.
- **Port already in use** — change `API_PORT` / `FRONT_PORT` in `.env`.
- **Job stuck "Downloading models"** — first run for a given language can take a minute; subsequent runs are instant.

## Limits

- Max upload: 200 MB
- Max pages: 500
- Job timeout: 30 minutes
- Job results auto-clean 1 hour after completion
```

- [ ] **Step 2: Run all tests one more time**

```bash
make test
```

Expected: backend pytest passes (engine tests may skip without tesseract / paddleocr), frontend vitest passes.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: troubleshooting and limits"
```

---

## Self-review notes

- **Spec coverage:** all sections of the spec map to tasks. Engines (Tasks 10–11), formats (Tasks 12–17), workers and CUDA (Tasks 11, 18), system info chip (Tasks 4, 20, 29), TTL cleanup (Tasks 6, 23), UI flow (Tasks 30–34), error handling tied to upload/job APIs (Tasks 19, 21), tests (Tasks 5–18, 35).
- **Out of scope per spec section 10** (batch, preview, DPI control, accounts, structure recovery, cloud engines) — intentionally absent.
- **Type consistency:** `JobState`, `OutputFormat`, `Engine`, etc. defined once in `app/jobs/models.py` (backend) and `lib/types.ts` (frontend); engine/formatter signatures consistent across `OcrEngine.run` (Task 7), `PaddleEngine.run` (Task 11), `OcrMyPdfEngine.run` (Task 10), `run_job` (Task 18).
- **Endpoint shapes** in the frontend client (Task 26) match backend responses (Tasks 19–22).
- The Paddle engine starts a fresh `PaddleOCR` instance per page in worker processes; this is intentionally simple — model load is amortized once per process within `ProcessPoolExecutor`, which keeps tasks below ~5 minutes for moderate documents but is the obvious next optimization if profiling shows a bottleneck.
