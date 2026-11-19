import httpx

import config


class SchedulingUnavailable(Exception):
    """Scheduling could not be reached, timed out, or failed on its side."""


class SchedulingRejected(Exception):
    """Scheduling answered, but said the window is invalid (400)."""


class SchedulingPollNotFound(SchedulingRejected):
    """Scheduling answered that the poll does not exist (404)."""


def error_detail(response, default):
    # Scheduling answers errors as JSON {"detail": ...}; anything else (e.g. an HTML error page) uses the default.
    try:
        return response.json().get("detail", default)
    except ValueError:
        return default


def describe_window(poll_id, start):
    url = f"{config.SCHEDULING_URL}/api/scheduling/polls/{poll_id}/windows/{start.isoformat()}"
    try:
        response = httpx.get(url, timeout=config.SCHEDULING_TIMEOUT_S)
    except httpx.HTTPError as error:
        raise SchedulingUnavailable(
            "The scheduling service is unavailable right now, so dates can't be confirmed. Try again in a minute."
        ) from error
    if response.status_code == 404:
        raise SchedulingPollNotFound(error_detail(response, f"Poll {poll_id} not found"))
    if response.status_code == 400:
        raise SchedulingRejected(error_detail(response, "Invalid window"))
    if response.status_code != 200:
        raise SchedulingUnavailable(
            f"The scheduling service failed (HTTP {response.status_code}), so dates can't be confirmed."
        )
    return response.json()
