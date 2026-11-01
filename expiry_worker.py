
import json
import logging
import signal
from collections.abc import Callable
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import settings


API_URL = (
    f"{settings.expiry_worker_api_url}/reservations/expire-due"
)

INTERVAL_SECONDS = settings.expiry_worker_interval_seconds
REQUEST_TIMEOUT_SECONDS = settings.expiry_worker_request_timeout_seconds
MAX_BACKOFF_SECONDS = settings.expiry_worker_max_backoff_seconds

MAX_RESPONSE_BYTES = 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("stockflow.expiry_worker")


class WorkerAuthenticationError(Exception):
    """Raised when worker credentials are rejected."""


class WorkerRequestError(Exception):
    """Raised when the expiry endpoint cannot be reached."""


class WorkerResponseError(Exception):
    """Raised when the endpoint returns an invalid response."""


def process_expired_reservations() -> int:
    """Call the expiry endpoint and return the number of expired reservations."""

    request = Request(
        API_URL,
        method="POST",
        headers={
            "X-Worker-Token": settings.worker_api_token,
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            raw_body = response.read(MAX_RESPONSE_BYTES + 1)

    except HTTPError as exc:
        if exc.code in (401, 403):
            raise WorkerAuthenticationError(
                f"Worker authentication rejected (HTTP {exc.code}). "
                "Check WORKER_API_TOKEN."
            ) from exc

        raise WorkerRequestError(
            f"Expiry endpoint returned HTTP {exc.code}."
        ) from exc

    except (URLError, TimeoutError, OSError) as exc:
        raise WorkerRequestError(
            f"Could not reach expiry endpoint: {exc}"
        ) from exc

    if len(raw_body) > MAX_RESPONSE_BYTES:
        raise WorkerResponseError(
            "Expiry endpoint response exceeded the allowed size."
        )

    try:
        result = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerResponseError(
            "Expiry endpoint returned invalid JSON."
        ) from exc

    if not isinstance(result, dict):
        raise WorkerResponseError(
            "Expiry endpoint response must be a JSON object."
        )

    count = result.get("expired_count")

    if type(count) is not int or count < 0:
        raise WorkerResponseError(
            "Expiry endpoint returned an invalid expired_count."
        )

    return count


def calculate_retry_delay(failure_count: int) -> int:
    """Calculate exponential backoff with a configured maximum."""

    if type(failure_count) is not int or failure_count < 1:
        raise ValueError("failure_count must be a positive integer.")

    delay = INTERVAL_SECONDS

    for _ in range(failure_count - 1):
        delay = min(delay * 2, MAX_BACKOFF_SECONDS)

        if delay >= MAX_BACKOFF_SECONDS:
            break

    return delay


def run_worker(
    stop_event: Event,
    processor: Callable[[], int] = process_expired_reservations,
) -> None:
    """Run the expiry polling loop until shutdown is requested."""

    failure_count = 0

    while not stop_event.is_set():
        try:
            expired_count = processor()

        except WorkerAuthenticationError as exc:
            failure_count += 1
            retry_delay = MAX_BACKOFF_SECONDS

            logger.error(
                "%s Retrying in %d seconds.",
                exc,
                retry_delay,
            )

        except (WorkerRequestError, WorkerResponseError) as exc:
            failure_count += 1
            retry_delay = calculate_retry_delay(failure_count)

            logger.warning(
                "%s Consecutive failures: %d. Retrying in %d seconds.",
                exc,
                failure_count,
                retry_delay,
            )

        else:
            failure_count = 0
            retry_delay = INTERVAL_SECONDS

            if expired_count > 0:
                logger.info(
                    "Expired and released stock for %d reservation(s).",
                    expired_count,
                )
            else:
                logger.debug("No expired reservations found.")

        # Event.wait allows shutdown to interrupt the waiting period.
        if stop_event.wait(retry_delay):
            break


def main() -> None:
    stop_event = Event()

    def handle_sigterm(signum, frame) -> None:
        logger.info("SIGTERM received; shutting down.")
        stop_event.set()

    previous_sigterm_handler = None

    if hasattr(signal, "SIGTERM"):
        previous_sigterm_handler = signal.signal(
            signal.SIGTERM,
            handle_sigterm,
        )

    logger.info(
        "StockFlow expiry worker started. "
        "Polling interval: %d seconds. Request timeout: %d seconds.",
        INTERVAL_SECONDS,
        REQUEST_TIMEOUT_SECONDS,
    )

    try:
        run_worker(stop_event)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received; shutting down.")

    finally:
        stop_event.set()

        if previous_sigterm_handler is not None:
            signal.signal(
                signal.SIGTERM,
                previous_sigterm_handler,
            )

        logger.info("StockFlow expiry worker stopped.")


if __name__ == "__main__":
    main()
