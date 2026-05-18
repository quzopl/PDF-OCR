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
