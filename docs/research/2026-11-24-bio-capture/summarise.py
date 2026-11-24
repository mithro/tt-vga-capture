# /// script
# requires-python = ">=3.11"
# ///
"""Tabulate run_capture_test.py JSON lines (one per run) into the two
Markdown tables used in the research note: pass/fail by clock period and
mode, and sample phase by data delay (tco).

Usage: uv run --no-project summarise.py runs/all.out
"""
import json
import re
import sys
from collections import defaultdict

rows = [json.loads(line) for line in open(sys.argv[1]) if line.startswith("{")]
rate = defaultdict(dict)
tco = defaultdict(dict)
for r in rows:
    m = re.match(r"rate-(\w+)-(rise|fall)-p([\d.]+)$", r["name"])
    if m:
        rate[float(m.group(3))][f"{m.group(1)} {m.group(2)}"] = (
            "pass" if r.get("ok") else "FAIL")
    m = re.match(r"tco-(single-rise-sb|single-rise|dual-rise)-(\d+)$", r["name"])
    if m:
        tco[int(m.group(2))][m.group(1)] = r.get("phase", "mixed") if r.get("ok") else "mixed"

cols = ["single rise", "single fall", "dual rise", "dual fall", "dual16 rise", "dual16 fall"]
print("| period (aclk) | pixel clock at 700 MHz | " + " | ".join(cols) + " |")
print("|---|---|" + "---|" * len(cols))
for p in sorted(rate, reverse=True):
    print(f"| {p:g} | {700 / p:.1f} MHz | " + " | ".join(rate[p].get(c, "-") for c in cols) + " |")
print()
tcols = ["single-rise", "single-rise-sb", "dual-rise"]
print("| tco (aclk after clock-pin edge) | " + " | ".join(tcols) + " |")
print("|---|" + "---|" * len(tcols))
for t in sorted(tco):
    print(f"| {t} | " + " | ".join(tco[t].get(c, "-") for c in tcols) + " |")
