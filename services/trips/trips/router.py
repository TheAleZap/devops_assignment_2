from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trips import service

router = APIRouter(prefix="/api/trips", tags=["trips"])

NOT_FOUND_ERRORS = (service.TripNotFoundError, service.TaskNotFoundError, service.PollNotFoundError)


Priority = Literal["low", "normal", "high"]


# ---------- Request bodies ----------

class TripCreate(BaseModel):
    name: str = Field(min_length=1)
    destination: str | None = None
    members: list[str] = []


class MemberAdd(BaseModel):
    name: str = Field(min_length=1)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    priority: Priority = "normal"


class TaskPriority(BaseModel):
    priority: Priority


class TaskClaim(BaseModel):
    member: str = Field(min_length=1)


class DatesConfirm(BaseModel):
    date_poll_id: int = Field(ge=1)
    start: date


# ---------- Response bodies (they define the shapes in openapi.json) ----------

class Member(BaseModel):
    id: int
    name: str


class Task(BaseModel):
    id: int
    title: str
    done: bool
    priority: Priority
    claimed_by: str | None


class Progress(BaseModel):
    total: int
    claimed: int
    done: int


class Window(BaseModel):
    # Same shape as the Scheduling service's Window, which Trips receives across the seam.
    start: date
    end: date
    available: list[str]
    missing: list[str]
    missed_days: int


class Trip(BaseModel):
    id: int
    name: str
    destination: str | None
    start_date: date | None
    end_date: date | None
    date_poll_id: int | None
    members: list[Member]
    tasks: list[Task]
    progress: Progress
    confirmed_window: Window | None = Field(default=None, description="Only set in the response to PUT /dates")


class ErrorResponse(BaseModel):
    detail: str


NOT_FOUND = {404: {"model": ErrorResponse, "description": "Trip, task or poll not found"}}
BAD_REQUEST = {400: {"model": ErrorResponse, "description": "Rejected by a business rule"}}
UNAVAILABLE = {503: {"model": ErrorResponse, "description": "The Scheduling service could not be reached"}}


def run(action, *args):
    try:
        return action(*args)
    except NOT_FOUND_ERRORS as error:
        raise HTTPException(status_code=404, detail=str(error))
    except service.SchedulingUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error))
    except service.TripsError as error:
        raise HTTPException(status_code=400, detail=str(error))


# ---------- Endpoints ----------

@router.post("", status_code=201, response_model=Trip, responses=BAD_REQUEST)
def create_trip(body: TripCreate):
    return run(service.create_trip, body.name, body.destination, body.members)


@router.get("/{trip_id}", response_model=Trip, responses=NOT_FOUND)
def get_trip(trip_id: int):
    return run(service.get_trip, trip_id)


@router.post("/{trip_id}/members", status_code=201, response_model=Trip, responses={**NOT_FOUND, **BAD_REQUEST})
def add_member(trip_id: int, body: MemberAdd):
    return run(service.add_member, trip_id, body.name)


@router.post("/{trip_id}/tasks", status_code=201, response_model=Trip, responses={**NOT_FOUND, **BAD_REQUEST})
def add_task(trip_id: int, body: TaskCreate):
    return run(service.add_task, trip_id, body.title, body.priority)


@router.put("/{trip_id}/tasks/{task_id}/priority", response_model=Trip, responses={**NOT_FOUND, **BAD_REQUEST})
def set_priority(trip_id: int, task_id: int, body: TaskPriority):
    return run(service.set_priority, trip_id, task_id, body.priority)


@router.post("/{trip_id}/tasks/{task_id}/claim", response_model=Trip, responses={**NOT_FOUND, **BAD_REQUEST})
def claim_task(trip_id: int, task_id: int, body: TaskClaim):
    return run(service.claim_task, trip_id, task_id, body.member)


@router.post("/{trip_id}/tasks/{task_id}/complete", response_model=Trip, responses={**NOT_FOUND, **BAD_REQUEST})
def complete_task(trip_id: int, task_id: int):
    return run(service.complete_task, trip_id, task_id)


@router.put(
    "/{trip_id}/dates",
    response_model=Trip,
    responses={**NOT_FOUND, **BAD_REQUEST, **UNAVAILABLE},
    summary="Confirm the trip's dates from a Scheduling poll (calls Scheduling across the seam)",
)
def confirm_dates(trip_id: int, body: DatesConfirm):
    return run(service.confirm_dates, trip_id, body.date_poll_id, body.start)
