import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import settings

API_URL = "http://127.0.0.1:8000/reservations/expire-due"
INTERVAL_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger("stockflow.expiry_worker")


def process_expired_reservations() -> None:
    request = Request(
        API_URL,
        method="POST",
        headers={"X-Worker-Token": settings.worker_api_token},
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))

        count = result.get("expired_count")

        if not isinstance(count, int):
            raise ValueError("Unexpected response from expiry endpoint.")

        if count > 0:
            logger.info("Expired and released stock for %d reservation(s).", count)

    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        logger.warning("Expiry check failed; will retry: %s", exc)


def main() -> None:
    logger.info(
        "StockFlow expiry worker started; checking every %d seconds.",
        INTERVAL_SECONDS,
    )

    try:
        while True:
            process_expired_reservations()
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("StockFlow expiry worker stopped.")


if __name__ == "__main__":
    main()
