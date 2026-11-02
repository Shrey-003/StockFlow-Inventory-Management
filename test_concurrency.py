import json
import sys
import threading
from getpass import getpass
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"
PRODUCT_ID = 6
INITIAL_STOCK = 10
REQUEST_COUNT = 5
QUANTITY_PER_REQUEST = 3


ACCESS_TOKEN = ""

def read_json_response(raw):
    if not raw:
        return {}

    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"raw": raw.decode("utf-8", errors="replace")}


def api_request(method, path, payload=None):
    data = None
    headers = (
        {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        if ACCESS_TOKEN
        else {}
    )

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=15) as response:
            return response.status, read_json_response(response.read())
    except HTTPError as exc:
        return exc.code, read_json_response(exc.read())


def reserve_at_same_time(barrier):
    barrier.wait(timeout=10)

    return api_request(
        "POST",
        f"/products/{PRODUCT_ID}/reservations",
        {
            "quantity": QUANTITY_PER_REQUEST,
            "ttl_minutes": 120,
        },
    )


def main():
    global ACCESS_TOKEN

    ACCESS_TOKEN = getpass(
        "Enter the current staff JWT (input hidden): "
    ).strip()

    if not ACCESS_TOKEN:
        print("ERROR: No access token provided.")
        sys.exit(1)
    reservation_ids = []
    passed = False
    final_stock = None

    try:
        # Confirm the test starts with the expected inventory.
        code, product = api_request(
            "GET", f"/products/{PRODUCT_ID}"
        )

        if code != 200:
            raise RuntimeError(f"Could not read test product: {code} {product}")

        if product.get("stock_quantity") != INITIAL_STOCK:
            raise RuntimeError(
                f"Expected stock {INITIAL_STOCK}, "
                f"found {product.get('stock_quantity')}. "
                "Stop and inspect the test product before proceeding."
            )

        print("Starting concurrent reservation test.")
        print(f"Product ID: {PRODUCT_ID}")
        print(f"Initial stock: {INITIAL_STOCK}")
        print(f"Concurrent requests: {REQUEST_COUNT}")
        print(f"Quantity per request: {QUANTITY_PER_REQUEST}")
        print()

        barrier = threading.Barrier(REQUEST_COUNT)

        with ThreadPoolExecutor(max_workers=REQUEST_COUNT) as executor:
            futures = [
                executor.submit(reserve_at_same_time, barrier)
                for _ in range(REQUEST_COUNT)
            ]
            results = [future.result() for future in futures]

        successes = [
            body for status, body in results if status == 201
        ]

        insufficient_stock = [
            body
            for status, body in results
            if status == 409
            and body.get("detail") == "Insufficient stock available."
        ]

        for index, (status, body) in enumerate(results, start=1):
            if status == 201:
                reservation_id = body.get("id")
                if isinstance(reservation_id, int):
                    reservation_ids.append(reservation_id)

                print(
                    f"Request {index}: HTTP {status} "
                    f"- reservation created, ID {reservation_id}"
                )
            else:
                print(
                    f"Request {index}: HTTP {status} "
                    f"- {body.get('detail', body)}"
                )

        code, product = api_request(
            "GET", f"/products/{PRODUCT_ID}"
        )

        if code != 200:
            raise RuntimeError(f"Could not verify stock: {code} {product}")

        stock_during_test = product.get("stock_quantity")

        print()
        print(f"Successful reservations: {len(successes)}")
        print(f"Insufficient-stock rejections: {len(insufficient_stock)}")
        print(f"Stock after concurrent requests: {stock_during_test}")

        passed = (
            len(successes) == 3
            and len(insufficient_stock) == 2
            and len(results) == REQUEST_COUNT
            and stock_during_test == 1
        )

    except Exception as exc:
        print(f"TEST ERROR: {exc}")

    finally:
        # Cancel only reservations created by this test.
        # This restores the test product to its initial stock.
        print()
        print("Cleaning up successful test reservations...")

        cleanup_ok = True

        for reservation_id in reservation_ids:
            try:
                code, body = api_request(
                    "POST",
                    f"/reservations/{reservation_id}/cancel",
                )

                if code == 200:
                    print(f"Reservation {reservation_id}: cancelled")
                else:
                    cleanup_ok = False
                    print(
                        f"Reservation {reservation_id}: "
                        f"cleanup failed ({code}) - {body}"
                    )
            except Exception as exc:
                cleanup_ok = False
                print(f"Cleanup error for reservation {reservation_id}: {exc}")

        try:
            code, product = api_request(
                "GET", f"/products/{PRODUCT_ID}"
            )

            if code == 200:
                final_stock = product.get("stock_quantity")
                print(f"Final stock after cleanup: {final_stock}")
            else:
                cleanup_ok = False
                print(f"Could not verify final stock: {code} {product}")
        except Exception as exc:
            cleanup_ok = False
            print(f"Final stock check failed: {exc}")

        passed = passed and cleanup_ok and final_stock == INITIAL_STOCK

        print()
        if passed:
            print("PASS: Concurrent reservations did not oversell stock.")
            print("PASS: Test reservations were cleaned up.")
        else:
            print("FAIL: Review the results and server logs before proceeding.")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
