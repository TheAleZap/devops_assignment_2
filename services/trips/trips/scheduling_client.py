import httpx

import config


class SchedulingUnavailable(Exception):
    """Scheduling could not be reached, timed out, or failed on its side."""


class SchedulingRejected(Exception):
    """Scheduling answered, but said the poll or window is invalid (400/404)."""


def describe_window(poll_id, start):
    url = f"{config.SCHEDULING_URL}/api/scheduling/polls/{poll_id}/windows/{start.isoformat()}"
    try:
        response = httpx.get(url, timeout=config.SCHEDULING_TIMEOUT_S)
    except httpx.HTTPError as error:
        raise SchedulingUnavailable(
            "The scheduling service is unavailable right now, so dates can't be confirmed. Try again in a minute."
        ) from error
    if response.status_code in (400, 404):
        raise SchedulingRejected(response.json().get("detail", "Invalid poll or window"))
    if response.status_code != 200:
        raise SchedulingUnavailable(
            f"The scheduling service failed (HTTP {response.status_code}), so dates can't be confirmed."
        )
    return response.json()
