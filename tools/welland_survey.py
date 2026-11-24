# SPDX-License-Identifier: Apache-2.0
"""Survey tinytapeout.fpgas.online and the Welland Pis for hardware this
project is waiting on, and say what changed since the last survey.

    uv run --no-project python tools/welland_survey.py [--state tmp/welland_survey.json]

Read-only throughout: it fetches public board pages and status.json, and runs
`cat`/`lsusb`/`ls` on each Pi over SSH through tweed. Looks for:

* a Raspberry Pi 5 with a Tiny Tapeout board (the RP1 capture backend);
* a USB VGA/HDMI capture card on any Pi (the reference to compare against);
* any camera or page that mentions a VGA screen;
* new boards or slugs on the site.

Exit status 0 always; the verdict lines start with FOUND or MISSING.
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import subprocess
import urllib.request

BASE = "https://tinytapeout.fpgas.online"
GATEWAY = "tweed.welland.mithis.com"
#: Every switch-2 port a Pi has been seen on; unreachable ones are reported.
PORTS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, *range(29, 49)]
#: USB IDs of common UVC capture dongles (MacroSilicon MS2109/MS2130 and
#: friends). Any `Video` interface or unknown /dev/video on a Pi 3/4 is also
#: reported, since a new device may not be in this list.
CAPTURE_USB_IDS = {"534d:2109", "534d:2130", "345f:2130", "1d6c:0103", "eba4:7588", "32ed:3200"}
TT_BOARD_USB = "2e8a:"
WORDS = re.compile(r"capture card|vga capture|usb vga|hdmi capture|vga screen|vga monitor|"
                   r"small screen|monitor|raspberry pi 5|pi 5\b|rp1", re.I)
PI_CMD = ("tr -d '\\0' < /proc/device-tree/model; echo; lsusb; "
          "echo '--video'; for d in /sys/class/video4linux/video*; do "
          "[ -e \"$d/name\" ] && echo \"$(basename $d) $(cat $d/name)\"; done")


def fetch(url: str) -> str:
    return urllib.request.urlopen(url, timeout=20).read().decode("utf-8", "replace")


def site() -> dict:
    index = fetch(BASE + "/")
    boards = {}
    for slug in sorted(set(re.findall(r'href="/board/([^/"]+)/"', index))):
        page = fetch(f"{BASE}/board/{slug}/")
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))
        try:
            status = json.loads(fetch(f"{BASE}/board/{slug}/status.json"))
        except Exception as exc:  # a board that is down answers with an error
            status = {"error": repr(exc)}
        board = status.get("board") or {}
        boards[slug] = {
            "pi": sorted(set(re.findall(r"pi-sw\d+-p\d+", page))),
            "reachable": status.get("reachable"),
            "chip": board.get("chip"),
            "usb_serial": board.get("usb_serial"),
            "words": sorted(set(m.group(0).lower() for m in WORDS.finditer(text))),
        }
    return boards


def pis() -> dict:
    found = {}
    for port in PORTS:
        try:
            r = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes", "-J", GATEWAY,
                 f"pi@10.21.2.{port}", PI_CMD],
                capture_output=True, text=True, timeout=45)
        except subprocess.TimeoutExpired:
            found[port] = {"up": False}
            continue
        if r.returncode != 0:
            found[port] = {"up": False}
            continue
        model, _, rest = r.stdout.partition("\n")
        usb, _, video = rest.partition("--video")
        found[port] = {
            "up": True,
            "model": model.strip(),
            "usb": sorted(l.split("ID ", 1)[1].strip() for l in usb.splitlines()
                          if "ID " in l and "hub" not in l.lower()),
            "video": sorted(v.strip() for v in video.splitlines() if v.strip()),
        }
    return found


def verdicts(boards: dict, hosts: dict) -> list[str]:
    out = []
    pi5_tt = [p for p, h in hosts.items() if h.get("up") and "Pi 5" in h.get("model", "")
              and any(u.startswith(TT_BOARD_USB) for u in h.get("usb", []))]
    out.append(("FOUND  Pi 5 with a Tiny Tapeout board on USB: %s" % pi5_tt) if pi5_tt else
               "MISSING Pi 5 with a Tiny Tapeout board on USB (a GPIO-wired one would not show here; "
               "check the site text below)")
    cards = [(p, u) for p, h in hosts.items() for u in h.get("usb", [])
             if u.split()[0].lower() in CAPTURE_USB_IDS or re.search(r"capture|video|ms2109|uvc", u, re.I)]
    out.append(("FOUND  USB capture device(s): %s" % cards) if cards else "MISSING USB VGA capture card")
    worded = {s: b["words"] for s, b in boards.items() if b["words"]}
    out.append(("NOTE   site pages mentioning capture/screen/Pi 5: %s" % worded) if worded else
               "MISSING any site page mentioning a capture card, VGA screen or Pi 5")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", type=pathlib.Path, default=pathlib.Path("tmp/welland_survey.json"))
    args = ap.parse_args()
    now = {"site": site(), "pis": {str(k): v for k, v in pis().items()}}
    for line in verdicts(now["site"], {int(k): v for k, v in now["pis"].items()}):
        print(line)
    print("\nPis up:")
    for port, h in sorted(now["pis"].items(), key=lambda kv: int(kv[0])):
        if h.get("up"):
            print(f"  p{port}: {h['model']}; usb {h['usb'] or '-'}; video {h['video'] or '-'}")
    print("Pis down/absent: " + " ".join(f"p{p}" for p, h in now["pis"].items() if not h.get("up")))
    if args.state.exists():
        old = json.loads(args.state.read_text())
        changes = []
        for part in ("site", "pis"):
            for key in sorted(set(old.get(part, {})) | set(now[part])):
                if old.get(part, {}).get(key) != now[part].get(key):
                    changes.append(f"  {part}/{key}: {old.get(part, {}).get(key)} -> {now[part].get(key)}")
        print("\nChanges since the last survey:" if changes else "\nNo changes since the last survey.")
        print("\n".join(changes))
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps(now, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
