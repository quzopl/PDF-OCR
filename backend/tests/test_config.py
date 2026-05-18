import os
from pathlib import Path

from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.api_port == 8114
    assert s.max_upload_mb == 200
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
