import shutil
from pathlib import Path

import pikepdf
import pytest
from fastapi.testclient import TestClient

from app.main import app

requires_qpdf = pytest.mark.skipif(
    shutil.which("qpdf") is None, reason="qpdf binary not installed"
)


@pytest.fixture
def encrypted_pdf(tmp_path: Path, text_pdf: Path) -> Path:
    out = tmp_path / "encrypted.pdf"
    with pikepdf.open(str(text_pdf)) as pdf:
        pdf.save(
            str(out),
            encryption=pikepdf.Encryption(user="secret", owner="secret", R=6),
        )
    return out


def _upload(client: TestClient, path: Path) -> dict:
    with path.open("rb") as f:
        r = client.post("/api/upload", files={"file": (path.name, f, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()


def test_upload_marks_encrypted(encrypted_pdf: Path):
    client = TestClient(app)
    body = _upload(client, encrypted_pdf)
    assert body["is_encrypted"] is True
    assert body["page_count"] == 0


@requires_qpdf
def test_unlock_with_correct_password(encrypted_pdf: Path):
    client = TestClient(app)
    upl = _upload(client, encrypted_pdf)
    r = client.post(
        "/api/unlock", json={"file_id": upl["file_id"], "password": "secret"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_encrypted"] is False
    assert body["page_count"] == 1


@requires_qpdf
def test_unlock_with_wrong_password(encrypted_pdf: Path):
    client = TestClient(app)
    upl = _upload(client, encrypted_pdf)
    r = client.post(
        "/api/unlock", json={"file_id": upl["file_id"], "password": "wrong"}
    )
    assert r.status_code == 400


def test_unlock_unknown_file_id():
    client = TestClient(app)
    r = client.post("/api/unlock", json={"file_id": "nope", "password": ""})
    assert r.status_code == 404


def test_upload_plain_pdf_not_encrypted(text_pdf: Path):
    client = TestClient(app)
    body = _upload(client, text_pdf)
    assert body["is_encrypted"] is False
    assert body["page_count"] == 1
