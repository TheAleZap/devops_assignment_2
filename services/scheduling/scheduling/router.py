from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from scheduling import service

router = APIRouter(prefix="/api/scheduling", tags=["scheduling"])


# ---------- Request bodies ----------

class PollCreate(BaseModel):
    title: str = Field(min_length=1)
    range_start: date
    range_end: date
    trip_length: int = Field(ge=1)


class AvailabilityUpdate(BaseModel):
    participant: str = Field(min_length=1)
    days: list[date]


# ---------- Response bodies (they define the shapes in openapi.json) ----------

class Poll(BaseModel):
    id: int
    title: str
    range_start: date
    range_end: date
    trip_length: int
    availability: dict[str, list[date]] = Field(description="Free days per participant")


class Window(BaseModel):
    start: date
    end: date
    available: list[str] = Field(description="Participants free on every day of the window")
    missing: list[str] = Field(description="Participants missing at least one day")
    missed_days: int = Field(description="Total days missed by the missing participants")


class ErrorResponse(BaseModel):
    detail: str


NOT_FOUND = {404: {"model": ErrorResponse, "description": "Poll not found"}}
BAD_REQUEST = {400: {"model": ErrorResponse, "description": "Rejected by a business rule"}}


# ---------- Endpoints ----------

@router.post("/polls", status_code=201, response_model=Poll, responses=BAD_REQUEST)
def create_poll(body: PollCreate):
    try:
        return service.create_poll(body.title, body.range_start, body.range_end, body.trip_length)
    except service.SchedulingError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/polls/{poll_id}", response_model=Poll, responses=NOT_FOUND)
def get_poll(poll_id: int):
    try:
        return service.get_poll(poll_id)
    except service.PollNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.put("/polls/{poll_id}/availability", response_model=Poll, responses={**NOT_FOUND, **BAD_REQUEST})
def set_availability(poll_id: int, body: AvailabilityUpdate):
    try:
        return service.set_availability(poll_id, body.participant, body.days)
    except service.PollNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except service.SchedulingError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/polls/{poll_id}/best-windows", response_model=list[Window], responses=NOT_FOUND)
def get_best_windows(poll_id: int, limit: int = Query(default=5, ge=1, le=20)):
    try:
        return service.get_best_windows(poll_id, limit)
    except service.PollNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.get(
    "/polls/{poll_id}/windows/{start}",
    response_model=Window,
    responses={**NOT_FOUND, **BAD_REQUEST},
    summary="Describe one window (called by the Trips service across the seam)",
)
def get_window(poll_id: int, start: date):
    try:
        return service.describe_window(poll_id, start)
    except service.PollNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except service.SchedulingError as error:
        raise HTTPException(status_code=400, detail=str(error))
