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
