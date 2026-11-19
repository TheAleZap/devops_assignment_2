"""HTTP-level tests: status codes and response shapes, through FastAPI's TestClient and a real database."""
import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture
def client(temp_db):
    # Not used as a context manager, so the startup migrations are not re-run; temp_db already migrated.
    return TestClient(app)


def create_poll(client, **overrides):
    body = {"title": "Ski", "range_start": "2026-12-01", "range_end": "2026-12-10", "trip_length": 3, **overrides}
    return client.post("/api/scheduling/polls", json=body)


def test_create_poll_returns_201_with_the_poll(client):
    response = create_poll(client)
    assert response.status_code == 201
    assert response.json()["title"] == "Ski"
    assert response.json()["availability"] == {}


def test_create_poll_with_blank_title_returns_400(client):
    response = create_poll(client, title="   ")
    assert response.status_code == 400
    assert "title" in response.json()["detail"]


def test_create_poll_with_missing_field_returns_422(client):
    response = client.post("/api/scheduling/polls", json={"title": "Ski"})
    assert response.status_code == 422


def test_unknown_poll_returns_404(client):
    response = client.get("/api/scheduling/polls/999999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Poll 999999 not found"}


def test_save_availability_and_rank_windows(client):
    poll_id = create_poll(client).json()["id"]
    days = {"participant": "Ana", "days": ["2026-12-02", "2026-12-03", "2026-12-04"]}
    saved = client.put(f"/api/scheduling/polls/{poll_id}/availability", json=days)
    assert saved.status_code == 200
    assert saved.json()["availability"] == {"Ana": ["2026-12-02", "2026-12-03", "2026-12-04"]}
    best = client.get(f"/api/scheduling/polls/{poll_id}/best-windows", params={"limit": 1})
    assert best.status_code == 200
    assert best.json()[0]["start"] == "2026-12-02"
    assert best.json()[0]["available"] == ["Ana"]


def test_availability_outside_the_range_returns_400(client):
    poll_id = create_poll(client).json()["id"]
    response = client.put(
        f"/api/scheduling/polls/{poll_id}/availability", json={"participant": "Ana", "days": ["2027-01-01"]}
    )
    assert response.status_code == 400


def test_window_endpoint_used_by_trips(client):
    poll_id = create_poll(client).json()["id"]
    response = client.get(f"/api/scheduling/polls/{poll_id}/windows/2026-12-02")
    assert response.status_code == 200
    assert set(response.json()) == {"start", "end", "available", "missing", "missed_days"}
    assert response.json()["end"] == "2026-12-04"


def test_window_outside_the_range_returns_400_and_unknown_poll_404(client):
    poll_id = create_poll(client).json()["id"]
    assert client.get(f"/api/scheduling/polls/{poll_id}/windows/2026-12-09").status_code == 400
    assert client.get("/api/scheduling/polls/999999/windows/2026-12-02").status_code == 404


def test_health_reports_the_database_and_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["db"] == "ok"
