
from io import BytesIO
from threading import Event
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

import expiry_worker as worker


def make_response(body: bytes):
    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    response.read.return_value = body
    return response


class StopAfterWaits:
    """Test double that stops the worker after a fixed number of waits."""

    def __init__(self, max_waits: int):
        self.max_waits = max_waits
        self.wait_calls = []

    def is_set(self) -> bool:
        return False

    def wait(self, seconds: int) -> bool:
        self.wait_calls.append(seconds)
        return len(self.wait_calls) >= self.max_waits


def test_process_expired_reservations_success():
    response = make_response(b'{"expired_count": 3}')

    with patch.object(
        worker,
        "urlopen",
        return_value=response,
    ) as mocked_urlopen:
        result = worker.process_expired_reservations()

    assert result == 3

    request = mocked_urlopen.call_args.args[0]
    timeout = mocked_urlopen.call_args.kwargs["timeout"]

    assert request.full_url == worker.API_URL
    assert request.get_method() == "POST"
    assert request.get_header("X-worker-token")
    assert request.get_header("Accept") == "application/json"
    assert timeout == worker.REQUEST_TIMEOUT_SECONDS

    response.read.assert_called_once_with(
        worker.MAX_RESPONSE_BYTES + 1
    )


@pytest.mark.parametrize(
    "status_code",
    [401, 403],
)
def test_process_expired_reservations_rejects_authentication_failure(
    status_code,
):
    error = HTTPError(
        worker.API_URL,
        status_code,
        "Authentication failed",
        None,
        BytesIO(b"Unauthorized"),
    )

    with patch.object(worker, "urlopen", side_effect=error):
        with pytest.raises(worker.WorkerAuthenticationError):
            worker.process_expired_reservations()


@pytest.mark.parametrize(
    "status_code",
    [400, 429, 500, 502, 503],
)
def test_process_expired_reservations_handles_http_errors(
    status_code,
):
    error = HTTPError(
        worker.API_URL,
        status_code,
        "HTTP failure",
        None,
        BytesIO(b"Request failed"),
    )

    with patch.object(worker, "urlopen", side_effect=error):
        with pytest.raises(worker.WorkerRequestError):
            worker.process_expired_reservations()


@pytest.mark.parametrize(
    "error",
    [
        URLError("Connection refused"),
        TimeoutError("Request timed out"),
        OSError("Network unavailable"),
    ],
)
def test_process_expired_reservations_handles_network_errors(error):
    with patch.object(worker, "urlopen", side_effect=error):
        with pytest.raises(worker.WorkerRequestError):
            worker.process_expired_reservations()


@pytest.mark.parametrize(
    "body",
    [
        b"invalid-json",
        b"[]",
        b"null",
        b"{}",
        b'{"expired_count": "3"}',
        b'{"expired_count": -1}',
        b'{"expired_count": 1.5}',
        b'{"expired_count": true}',
    ],
)
def test_process_expired_reservations_rejects_invalid_responses(body):
    response = make_response(body)

    with patch.object(worker, "urlopen", return_value=response):
        with pytest.raises(worker.WorkerResponseError):
            worker.process_expired_reservations()


def test_process_expired_reservations_rejects_oversized_response():
    response = make_response(
        b"x" * (worker.MAX_RESPONSE_BYTES + 1)
    )

    with patch.object(worker, "urlopen", return_value=response):
        with pytest.raises(
            worker.WorkerResponseError,
            match="exceeded the allowed size",
        ):
            worker.process_expired_reservations()


@pytest.mark.parametrize(
    ("failure_count", "expected_delay"),
    [
        (1, 30),
        (2, 60),
        (3, 120),
        (4, 240),
        (5, 300),
        (6, 300),
        (10, 300),
    ],
)
def test_calculate_retry_delay(
    failure_count,
    expected_delay,
):
    assert worker.calculate_retry_delay(failure_count) == (
        expected_delay
    )


@pytest.mark.parametrize(
    "failure_count",
    [0, -1, 1.5, True],
)
def test_calculate_retry_delay_rejects_invalid_failure_count(
    failure_count,
):
    with pytest.raises(ValueError):
        worker.calculate_retry_delay(failure_count)


def test_worker_uses_exponential_backoff():
    def failing_processor():
        raise worker.WorkerRequestError("Connection unavailable")

    stop_event = StopAfterWaits(max_waits=5)

    worker.run_worker(
        stop_event,
        processor=failing_processor,
    )

    assert stop_event.wait_calls == [
        30,
        60,
        120,
        240,
        300,
    ]


def test_worker_uses_maximum_backoff_for_authentication_failure():
    def failing_processor():
        raise worker.WorkerAuthenticationError("Invalid worker token")

    stop_event = StopAfterWaits(max_waits=2)

    worker.run_worker(
        stop_event,
        processor=failing_processor,
    )

    assert stop_event.wait_calls == [
        worker.MAX_BACKOFF_SECONDS,
        worker.MAX_BACKOFF_SECONDS,
    ]


def test_worker_resets_backoff_after_success():
    outcomes = [
        worker.WorkerRequestError("First failure"),
        worker.WorkerRequestError("Second failure"),
        0,
        worker.WorkerRequestError("Failure after recovery"),
    ]

    def processor():
        outcome = outcomes.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome

    stop_event = StopAfterWaits(max_waits=4)

    worker.run_worker(
        stop_event,
        processor=processor,
    )

    assert stop_event.wait_calls == [
        30,
        60,
        30,
        30,
    ]


def test_worker_stops_without_processing_when_already_stopped():
    stop_event = Event()
    stop_event.set()

    processor = MagicMock(return_value=0)

    worker.run_worker(
        stop_event,
        processor=processor,
    )

    processor.assert_not_called()


def test_worker_stops_after_shutdown_during_wait():
    stop_event = StopAfterWaits(max_waits=1)
    processor = MagicMock(return_value=0)

    worker.run_worker(
        stop_event,
        processor=processor,
    )

    processor.assert_called_once_with()
    assert stop_event.wait_calls == [worker.INTERVAL_SECONDS]
