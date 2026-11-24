# SPDX-License-Identifier: Apache-2.0
"""Print each tinytapeout.fpgas.online board's live status, one line a board.

Read-only: fetches the public index and every `/board/<slug>/status.json`.
Run before claiming a board, to see outside clients and what is loaded.

    uv run --no-project python tools/board_clients.py
"""

from __future__ import annotations

import json
import re
import urllib.request

BASE = "https://tinytapeout.fpgas.online"


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "board-clients/1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", "replace")


def flatten(prefix: str, value, out: dict) -> None:
    if isinstance(value, dict):
        for key, inner in value.items():
            flatten(f"{prefix}.{key}" if prefix else key, inner, out)
    else:
        out[prefix] = value


def main() -> None:
    index = fetch(BASE + "/")
    for slug in sorted(set(re.findall(r'href="/board/([^/"]+)/"', index))):
        try:
            status = json.loads(fetch(f"{BASE}/board/{slug}/status.json"))
        except Exception as exc:  # report and carry on with the next board
            print(f"{slug}: status unavailable: {exc}")
            continue
        flat: dict = {}
        flatten("", status, flat)
        keep = {
            key: value
            for key, value in flat.items()
            if re.search(r"client|state|enabled|design|serial|host|port|name|up", key)
        }
        print(f"{slug}: {json.dumps(keep, sort_keys=True)}")


if __name__ == "__main__":
    main()
