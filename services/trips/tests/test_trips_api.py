"""HTTP-level tests: status codes and response shapes, through FastAPI's TestClient and a real database.
Scheduling is stubbed here; the real cross-service call is covered by tests/integration."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import app
from trips import scheduling_client


@pytest.fixture
def client(temp_db):
    # Not used as a context manager, so the startup migrations are not re-run; temp_db already migrated.
    return TestClient(app)


def create_trip(client, **overrides):
    return client.post("/api/trips", json={"name": "Andorra", "members": ["Ana", "Ben"], **overrides})


def test_create_trip_returns_201_with_members_and_progress(client):
    response = create_trip(client)
    assert response.status_code == 201
    assert [member["name"] for member in response.json()["members"]] == ["Ana", "Ben"]
    assert response.json()["progress"] == {"total": 0, "claimed": 0, "done": 0}


def test_unknown_trip_returns_404(client):
    response = client.get("/api/trips/999999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Trip 999999 not found"}


def test_task_board_flow(client):
    trip_id = create_trip(client).json()["id"]
    task_id = client.post(f"/api/trips/{trip_id}/tasks", json={"title": "Book flat"}).json()["tasks"][0]["id"]
    assert client.post(f"/api/trips/{trip_id}/tasks/{task_id}/complete").status_code == 400
    claimed = client.post(f"/api/trips/{trip_id}/tasks/{task_id}/claim", json={"member": "ana"})
    assert claimed.json()["tasks"][0]["claimed_by"] == "Ana"
    done = client.post(f"/api/trips/{trip_id}/tasks/{task_id}/complete")
    assert done.json()["progress"] == {"total": 1, "claimed": 1, "done": 1}


def test_non_member_cannot_claim_returns_400(client):
    trip_id = create_trip(client).json()["id"]
    task_id = client.post(f"/api/trips/{trip_id}/tasks", json={"title": "Book flat"}).json()["tasks"][0]["id"]
    response = client.post(f"/api/trips/{trip_id}/tasks/{task_id}/claim", json={"member": "Carla"})
    assert response.status_code == 400


def test_add_member_twice_returns_400(client):
    trip_id = create_trip(client).json()["id"]
    assert client.post(f"/api/trips/{trip_id}/members", json={"name": "Cleo"}).status_code == 201
    assert client.post(f"/api/trips/{trip_id}/members", json={"name": "cleo"}).status_code == 400


def stub_scheduling(monkeypatch, outcome):
    def describe_window(poll_id, start):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(scheduling_client, "describe_window", describe_window)


def confirm(client, trip_id):
    return client.put(f"/api/trips/{trip_id}/dates", json={"date_poll_id": 1, "start": date(2026, 12, 2).isoformat()})


def test_confirm_dates_returns_200_with_the_window(client, monkeypatch):
    window = {"start": "2026-12-02", "end": "2026-12-04", "available": ["Ana"], "missing": [], "missed_days": 0}
    stub_scheduling(monkeypatch, window)
    response = confirm(client, create_trip(client).json()["id"])
    assert response.status_code == 200
    assert response.json()["start_date"] == "2026-12-02"
    assert response.json()["confirmed_window"] == window


def test_confirm_dates_maps_scheduling_errors_to_status_codes(client, monkeypatch):
    trip_id = create_trip(client).json()["id"]
    stub_scheduling(monkeypatch, scheduling_client.SchedulingPollNotFound("Poll 1 not found"))
    assert confirm(client, trip_id).status_code == 404
    stub_scheduling(monkeypatch, scheduling_client.SchedulingRejected("outside the range"))
    assert confirm(client, trip_id).status_code == 400
    stub_scheduling(monkeypatch, scheduling_client.SchedulingUnavailable("Scheduling is down"))
    response = confirm(client, trip_id)
    assert response.status_code == 503
    assert response.json() == {"detail": "Scheduling is down"}


def test_health_reports_the_database_and_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["db"] == "ok"


def test_add_task_accepts_a_priority_and_rejects_unknown_ones(client):
    trip_id = create_trip(client).json()["id"]
    response = client.post(f"/api/trips/{trip_id}/tasks", json={"title": "Lift passes", "priority": "high"})
    assert response.json()["tasks"][0]["priority"] == "high"
    bad = client.post(f"/api/trips/{trip_id}/tasks", json={"title": "X", "priority": "urgent"})
    assert bad.status_code == 422


def test_set_priority_returns_200_and_422_for_unknown_values(client):
    trip_id = create_trip(client).json()["id"]
    task_id = client.post(f"/api/trips/{trip_id}/tasks", json={"title": "Lift passes"}).json()["tasks"][0]["id"]
    response = client.put(f"/api/trips/{trip_id}/tasks/{task_id}/priority", json={"priority": "high"})
    assert response.status_code == 200
    assert response.json()["tasks"][0]["priority"] == "high"
    bad = client.put(f"/api/trips/{trip_id}/tasks/{task_id}/priority", json={"priority": "urgent"})
    assert bad.status_code == 422
