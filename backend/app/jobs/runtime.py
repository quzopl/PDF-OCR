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
