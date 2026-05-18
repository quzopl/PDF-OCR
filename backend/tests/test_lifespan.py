import asyncio

from fastapi.testclient import TestClient

from app.main import app


def test_app_starts_with_sweeper():
    with TestClient(app) as client:
        # if lifespan crashes, this with-block raises
        assert client.get("/api/health").status_code == 200
