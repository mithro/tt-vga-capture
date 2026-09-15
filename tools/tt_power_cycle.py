# SPDX-License-Identifier: Apache-2.0
"""Power-cycle one Welland Tiny Tapeout Pi through the fpgas.online PoE API
and wait for its daemon to come back.

    uv run --no-project tools/tt_power_cycle.py --port 7 --switch 2 \
        --health http://127.0.0.1:18765/health

The toggle endpoint (fpgas.online-poe `snmp_switch.views.toggle`) turns the
PoE port off, waits 0.5 s and turns it on again. Only ever cycle one board
at a time, and leave a gap between boards.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

TOGGLE_URL = "https://welland.fpgas.online/snmp/toggle"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--switch", type=int, default=2)
    ap.add_argument("--health", help="daemon health URL to poll afterwards")
    ap.add_argument("--wait", type=int, default=240, help="seconds to wait for health")
    a = ap.parse_args()

    body = json.dumps({"port": str(a.port), "switch": a.switch}).encode()
    req = urllib.request.Request(TOGGLE_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print("toggle:", r.status, r.read().decode())
    except urllib.error.HTTPError as e:
        print("toggle failed:", e.code, e.read().decode(), file=sys.stderr)
        return 1
    if not a.health:
        return 0
    t0 = time.time()
    while time.time() - t0 < a.wait:
        try:
            with urllib.request.urlopen(a.health, timeout=5) as r:
                print(f"health after {time.time() - t0:.0f}s:", r.read().decode()[:120])
                return 0
        except Exception as e:  # noqa: BLE001 - polling
            last = e
        time.sleep(5)
    print("no health within", a.wait, "s:", last, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
