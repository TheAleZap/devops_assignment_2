from datetime import date

import httpx
import pytest

from trips import scheduling_client

START = date(2026, 10, 4)


def fake_get(status_code=200, json=None, text=None, error=None):
    def get(url, timeout):
        if error is not None:
            raise error
        request = httpx.Request("GET", url)
        if text is not None:
            return httpx.Response(status_code, text=text, request=request)
        return httpx.Response(status_code, json=json, request=request)
    return get


def test_returns_the_window_when_scheduling_answers_200(monkeypatch):
    window = {"start": "2026-10-04", "end": "2026-10-06", "available": ["Ana"], "missing": [], "missed_days": 0}
    monkeypatch.setattr(scheduling_client.httpx, "get", fake_get(200, json=window))
    assert scheduling_client.describe_window(1, START) == window


def test_calls_the_window_endpoint_with_the_configured_timeout(monkeypatch):
    seen = {}

    def get(url, timeout):
        seen["url"], seen["timeout"] = url, timeout
        return httpx.Response(200, json={}, request=httpx.Request("GET", url))

    monkeypatch.setattr(scheduling_client.config, "SCHEDULING_URL", "http://scheduling:8001")
    monkeypatch.setattr(scheduling_client.config, "SCHEDULING_TIMEOUT_S", 2.0)
    monkeypatch.setattr(scheduling_client.httpx, "get", get)
    scheduling_client.describe_window(7, START)
    assert seen == {"url": "http://scheduling:8001/api/scheduling/polls/7/windows/2026-10-04", "timeout": 2.0}


def test_404_means_the_poll_does_not_exist(monkeypatch):
    monkeypatch.setattr(scheduling_client.httpx, "get", fake_get(404, json={"detail": "Poll 9 not found"}))
    with pytest.raises(scheduling_client.SchedulingPollNotFound, match="Poll 9 not found"):
        scheduling_client.describe_window(9, START)


def test_400_means_the_window_is_invalid(monkeypatch):
    monkeypatch.setattr(scheduling_client.httpx, "get", fake_get(400, json={"detail": "outside the range"}))
    with pytest.raises(scheduling_client.SchedulingRejected) as raised:
        scheduling_client.describe_window(1, START)
    assert not isinstance(raised.value, scheduling_client.SchedulingPollNotFound)


def test_error_page_that_is_not_json_still_gives_a_clear_error(monkeypatch):
    monkeypatch.setattr(scheduling_client.httpx, "get", fake_get(404, text="<html>Not Found</html>"))
    with pytest.raises(scheduling_client.SchedulingPollNotFound, match="Poll 1 not found"):
        scheduling_client.describe_window(1, START)


def test_server_error_means_scheduling_is_unavailable(monkeypatch):
    monkeypatch.setattr(scheduling_client.httpx, "get", fake_get(500, text="boom"))
    with pytest.raises(scheduling_client.SchedulingUnavailable):
        scheduling_client.describe_window(1, START)


@pytest.mark.parametrize("error", [httpx.ConnectError("refused"), httpx.ReadTimeout("too slow")])
def test_connection_errors_and_timeouts_mean_scheduling_is_unavailable(monkeypatch, error):
    monkeypatch.setattr(scheduling_client.httpx, "get", fake_get(error=error))
    with pytest.raises(scheduling_client.SchedulingUnavailable):
        scheduling_client.describe_window(1, START)
