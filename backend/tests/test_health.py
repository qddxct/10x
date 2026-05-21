from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_returns_ok_with_db_status():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["db"] in {"ok", "down"}


def test_root_redirects_to_docs():
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"] == "/docs"
