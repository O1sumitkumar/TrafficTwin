from fastapi.testclient import TestClient

from api.main import app


def test_health() -> None:
    body = TestClient(app).get("/health").json()
    assert body["status"] == "ok"
    assert body["label"] == "synthetic demand, uncalibrated"
