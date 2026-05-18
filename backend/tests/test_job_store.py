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
