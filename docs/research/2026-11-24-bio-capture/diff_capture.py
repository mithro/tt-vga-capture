# /// script
# requires-python = ">=3.11"
# ///
"""Diagnostic: list where a capture log diverges from the injected data.

Usage: uv run --no-project diff_capture.py LOG CLOCKS SEED [OFFSET]
Regenerates data with the same RNG as run_capture_test.py.
"""
import random
import re
import sys
from pathlib import Path

log, clocks, seed = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
off = int(sys.argv[4]) if len(sys.argv) > 4 else 0
rng = random.Random(seed)
data = [rng.randrange(256) for _ in range(clocks)]
got = []
for line in log.read_text().splitlines():
    m = re.match(r"\[fifo_drain\]\s+\[\d+\] = 0x([0-9a-f]{8})", line)
    if m:
        w = int(m.group(1), 16)
        got += [(w >> (8 * i)) & 0xFF for i in range(4)]
bad = [i for i, (a, b) in enumerate(zip(got, data[off:])) if a != b]
print(f"samples={len(got)} mismatches={len(bad)} first={bad[:20]}")
for i in bad[:3]:
    lo = max(0, i - 3)
    print(i, "got", [hex(x) for x in got[lo:i + 5]], "exp", [hex(x) for x in data[off + lo:off + i + 5]])
# Locate each mismatching sample's true index, if it appears nearby.
for i in bad[:10]:
    near = [j - (off + i) for j in range(max(0, off + i - 8), min(len(data), off + i + 9)) if data[j] == got[i]]
    print(f"sample {i}: value {got[i]:#04x} found at relative edge {near}")
