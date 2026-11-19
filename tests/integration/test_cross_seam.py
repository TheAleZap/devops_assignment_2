"""Cross-seam integration test: runs against the real system started with `docker compose up`.

Trips calls Scheduling over HTTP inside compose (SCHEDULING_URL=http://scheduling:8001), so these tests
exercise the real network call, both databases, and the designed failure when Scheduling is stopped.
Run locally from the repo root, with the stack up:  python -m pytest tests/integration -v
"""
import os
import subprocess
import time

import httpx
import pytest

SCHEDULING = os.environ.get("SCHEDULING_BASE_URL", "http://localhost:8001")
TRIPS = os.environ.get("TRIPS_BASE_URL", "http://localhost:8002")


def wait_until_healthy(base_url, seconds=180):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if httpx.get(f"{base_url}/health", timeout=3).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    pytest.fail(f"{base_url} did not become healthy within {seconds}s")


@pytest.fixture(scope="module", autouse=True)
def system_is_up():
    wait_until_healthy(SCHEDULING)
    wait_until_healthy(TRIPS)


def create_poll_with_availability():
    poll = httpx.post(
        f"{SCHEDULING}/api/scheduling/polls",
        json={"title": "Integration", "range_start": "2026-12-01", "range_end": "2026-12-10", "trip_length": 3},
    ).json()
    httpx.put(
        f"{SCHEDULING}/api/scheduling/polls/{poll['id']}/availability",
        json={"participant": "Ana", "days": ["2026-12-02", "2026-12-03", "2026-12-04"]},
    ).raise_for_status()
    return poll["id"]


def create_trip():
    return httpx.post(f"{TRIPS}/api/trips", json={"name": "Integration trip", "members": ["Ana"]}).json()["id"]


def confirm_dates(trip_id, poll_id, start="2026-12-02"):
    return httpx.put(
        f"{TRIPS}/api/trips/{trip_id}/dates", json={"date_poll_id": poll_id, "start": start}, timeout=15
    )


def test_confirming_dates_calls_scheduling_and_stores_the_window():
    poll_id = create_poll_with_availability()
    response = confirm_dates(create_trip(), poll_id)
    assert response.status_code == 200
    body = response.json()
    assert (body["start_date"], body["end_date"], body["date_poll_id"]) == ("2026-12-02", "2026-12-04", poll_id)
    assert body["confirmed_window"]["available"] == ["Ana"]


def test_unknown_poll_is_a_404_across_the_seam():
    response = confirm_dates(create_trip(), 999999)
    assert response.status_code == 404


def test_window_outside_the_poll_is_a_400_across_the_seam():
    response = confirm_dates(create_trip(), create_poll_with_availability(), start="2026-12-09")
    assert response.status_code == 400


def test_trips_keeps_working_and_fails_cleanly_while_scheduling_is_stopped():
    poll_id = create_poll_with_availability()
    trip_id = create_trip()
    subprocess.run(["docker", "compose", "stop", "scheduling"], check=True)
    try:
        started = time.time()
        response = confirm_dates(trip_id, poll_id)
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"]
        assert time.time() - started < 12, "the call must fail fast, not hang"
        assert httpx.get(f"{TRIPS}/health").status_code == 200
        unchanged = httpx.get(f"{TRIPS}/api/trips/{trip_id}").json()
        assert unchanged["start_date"] is None
    finally:
        subprocess.run(["docker", "compose", "start", "scheduling"], check=True)
