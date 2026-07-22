import time
import sys
import requests

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 120
INTERVAL = 0.5

total = 0
success = 0
fail = 0
outage_start = None
outage_duration = 0.0


def report():
    rate = (success / total * 100) if total > 0 else 0
    print()
    print(f"=== Chaos Test Report ===")
    print(f"  Duration: {DURATION}s")
    print(f"  Total requests: {total}")
    print(f"  Success: {success}")
    print(f"  Failures: {fail}")
    print(f"  Success rate: {rate:.1f}%")
    print(f"  Max outage: {outage_duration:.1f}s")


deadline = time.time() + DURATION

while time.time() < deadline:
    total += 1
    try:
        r = requests.post(f"{BASE_URL}/items", json={"name": f"chaos-{total}"}, timeout=10)
        if r.status_code in (200, 201):
            success += 1
            if outage_start is not None:
                outage_duration = max(outage_duration, time.time() - outage_start)
                outage_start = None
            item_id = r.json().get("id")
        else:
            fail += 1
            if outage_start is None:
                outage_start = time.time()
    except Exception:
        fail += 1
        if outage_start is None:
            outage_start = time.time()

    time.sleep(INTERVAL)

    if item_id:
        total += 1
        try:
            r = requests.get(f"{BASE_URL}/items/{item_id}", timeout=10)
            if r.status_code == 200:
                success += 1
                if outage_start is not None:
                    outage_duration = max(outage_duration, time.time() - outage_start)
                    outage_start = None
            else:
                fail += 1
                if outage_start is None:
                    outage_start = time.time()
        except Exception:
            fail += 1
            if outage_start is None:
                outage_start = time.time()

        time.sleep(INTERVAL)

    if item_id:
        total += 1
        try:
            r = requests.delete(f"{BASE_URL}/items/{item_id}", timeout=10)
            if r.status_code == 200:
                success += 1
                if outage_start is not None:
                    outage_duration = max(outage_duration, time.time() - outage_start)
                    outage_start = None
            else:
                fail += 1
                if outage_start is None:
                    outage_start = time.time()
        except Exception:
            fail += 1
            if outage_start is None:
                outage_start = time.time()

        item_id = None
        time.sleep(INTERVAL)

report()
