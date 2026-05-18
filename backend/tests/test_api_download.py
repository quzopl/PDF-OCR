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
