from fastapi.testclient import TestClient

from app.main import app


def test_system_info():
    client = TestClient(app)
    r = client.get("/api/system/info")
    assert r.status_code == 200
    body = r.json()
    assert body["cpu"]["count"] >= 1
    assert "ram" in body and "gpu" in body
