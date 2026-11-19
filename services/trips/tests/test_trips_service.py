from datetime import date

import pytest

from trips import scheduling_client
from trips import service


# --- pure helpers ---

def test_clean_name_trims_whitespace():
    assert service.clean_name("  Lisbon trip  ") == "Lisbon trip"


def test_clean_name_rejects_blank():
    with pytest.raises(service.TripsError):
        service.clean_name("   ")


def test_unique_names_ignores_case_and_keeps_first_spelling():
    assert service.unique_names(["Marta", "marta", " Pablo "]) == ["Marta", "Pablo"]


def test_find_member_is_case_insensitive():
    members = [{"id": 1, "name": "Marta"}]
    assert service.find_member(members, " marta ") == {"id": 1, "name": "Marta"}
    assert service.find_member(members, "Pablo") is None


def test_find_task_raises_for_unknown_task():
    with pytest.raises(service.TaskNotFoundError):
        service.find_task([{"id": 1}], 2)


def test_summarize_tasks_counts_claimed_and_done():
    tasks = [
        {"claimed_by": "Marta", "done": True},
        {"claimed_by": "Pablo", "done": False},
        {"claimed_by": None, "done": False},
    ]
    assert service.summarize_tasks(tasks) == {"total": 3, "claimed": 2, "done": 1}


# --- trips and members ---

def test_create_trip_removes_duplicate_members_and_blank_destination(temp_db):
    trip = service.create_trip("Autumn", "   ", ["Ana", "ana", "Ben"])
    assert trip["destination"] is None
    assert [member["name"] for member in trip["members"]] == ["Ana", "Ben"]
    assert trip["progress"] == {"total": 0, "claimed": 0, "done": 0}


def test_get_trip_raises_when_trip_does_not_exist(temp_db):
    with pytest.raises(service.TripNotFoundError):
        service.get_trip(999)


def test_add_member_adds_a_new_person(temp_db):
    trip = service.create_trip("Autumn", members=["Ana"])
    updated = service.add_member(trip["id"], "Ben")
    assert [member["name"] for member in updated["members"]] == ["Ana", "Ben"]


def test_add_member_rejects_duplicate_name_in_any_case(temp_db):
    trip = service.create_trip("Autumn", members=["Ana"])
    with pytest.raises(service.TripsError):
        service.add_member(trip["id"], "ANA")


# --- task board ---

@pytest.fixture
def trip_with_task(temp_db):
    trip = service.create_trip("Autumn", members=["Ana", "Ben"])
    trip = service.add_task(trip["id"], "Book Airbnb")
    return trip["id"], trip["tasks"][0]["id"]


def test_add_task_rejects_blank_title(temp_db):
    trip = service.create_trip("Autumn")
    with pytest.raises(service.TripsError):
        service.add_task(trip["id"], "   ")


def test_member_can_claim_task_case_insensitively(trip_with_task):
    trip_id, task_id = trip_with_task
    trip = service.claim_task(trip_id, task_id, "ana")
    assert trip["tasks"][0]["claimed_by"] == "Ana"
    assert trip["progress"]["claimed"] == 1


def test_non_member_cannot_claim_task(trip_with_task):
    trip_id, task_id = trip_with_task
    with pytest.raises(service.TripsError):
        service.claim_task(trip_id, task_id, "Carla")


def test_task_claimed_by_someone_else_cannot_be_taken_over(trip_with_task):
    trip_id, task_id = trip_with_task
    service.claim_task(trip_id, task_id, "Ana")
    with pytest.raises(service.TripsError):
        service.claim_task(trip_id, task_id, "Ben")


def test_same_member_can_claim_their_own_task_again(trip_with_task):
    trip_id, task_id = trip_with_task
    service.claim_task(trip_id, task_id, "Ana")
    trip = service.claim_task(trip_id, task_id, "Ana")
    assert trip["tasks"][0]["claimed_by"] == "Ana"


def test_unclaimed_task_cannot_be_completed(trip_with_task):
    trip_id, task_id = trip_with_task
    with pytest.raises(service.TripsError):
        service.complete_task(trip_id, task_id)


def test_claimed_task_can_be_completed(trip_with_task):
    trip_id, task_id = trip_with_task
    service.claim_task(trip_id, task_id, "Ana")
    trip = service.complete_task(trip_id, task_id)
    assert trip["tasks"][0]["done"] is True
    assert trip["progress"]["done"] == 1


def test_task_from_another_trip_is_not_found(trip_with_task):
    _, task_id = trip_with_task
    other_trip = service.create_trip("Other", members=["Ana"])
    with pytest.raises(service.TaskNotFoundError):
        service.claim_task(other_trip["id"], task_id, "Ana")


# --- confirming dates (the seam; Scheduling is stubbed, see ADR-9) ---

WINDOW = {"start": "2026-10-04", "end": "2026-10-06", "available": ["Ana"], "missing": [], "missed_days": 0}


def test_confirm_dates_stores_window_and_returns_attendance(temp_db, monkeypatch):
    monkeypatch.setattr(scheduling_client, "describe_window", lambda poll_id, start: WINDOW)
    trip = service.create_trip("Autumn", members=["Ana"])
    updated = service.confirm_dates(trip["id"], 7, date(2026, 10, 4))
    assert (updated["start_date"], updated["end_date"]) == ("2026-10-04", "2026-10-06")
    assert updated["date_poll_id"] == 7
    assert updated["confirmed_window"]["available"] == ["Ana"]


def test_confirm_dates_turns_rejected_window_into_trips_error(temp_db, monkeypatch):
    def reject(poll_id, start):
        raise scheduling_client.SchedulingRejected("That window falls outside the poll's date range")
    monkeypatch.setattr(scheduling_client, "describe_window", reject)
    trip = service.create_trip("Autumn")
    with pytest.raises(service.TripsError):
        service.confirm_dates(trip["id"], 999, date(2026, 10, 4))


def test_confirm_dates_when_scheduling_is_down_leaves_trip_unchanged(temp_db, monkeypatch):
    def down(poll_id, start):
        raise scheduling_client.SchedulingUnavailable("Scheduling service is unavailable")
    monkeypatch.setattr(scheduling_client, "describe_window", down)
    trip = service.create_trip("Autumn")
    with pytest.raises(service.SchedulingUnavailableError):
        service.confirm_dates(trip["id"], 1, date(2026, 10, 4))
    assert service.get_trip(trip["id"])["start_date"] is None


def test_confirm_dates_with_unknown_poll_raises_poll_not_found(temp_db, monkeypatch):
    # A1 feedback: an unknown poll returned 400; it is now a 404 (PollNotFoundError is in NOT_FOUND_ERRORS).
    def missing(poll_id, start):
        raise scheduling_client.SchedulingPollNotFound("Poll 999 not found")
    monkeypatch.setattr(scheduling_client, "describe_window", missing)
    trip = service.create_trip("Autumn")
    with pytest.raises(service.PollNotFoundError):
        service.confirm_dates(trip["id"], 999, date(2026, 10, 4))
