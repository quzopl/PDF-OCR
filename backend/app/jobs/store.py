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
