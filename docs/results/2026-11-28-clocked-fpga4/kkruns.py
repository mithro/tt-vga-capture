"""Runs of consecutive differing clocks: per frame, the start column and length of each run on each line."""
import sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from vgacap.stream import read_stream
from tthfv import compare, reference
from tthfv.board.capture_file import _to_uo_out
ref = compare.load_reference(reference.reference_dir(sys.argv[1], "fpga-4"))
h, items = read_stream(Path(sys.argv[2]).read_bytes())
v = [i[1] for i in items if i[0] == "run"]; c = [i[2] for i in items if i[0] == "run"]
uo = _to_uo_out(np.repeat(np.asarray(v, np.uint64), np.asarray(c, np.int64)), h.signal_map, h.sample_bits)
fc = compare.frame_clocks(ref.meta); lc = ref.meta["line_clocks"]
n = min(len(uo), len(ref.samples)); d = [int(x) for x in np.nonzero(uo[:n] != ref.samples[:n])[0]]
runs = []
for x in d:
    if runs and x == runs[-1][0] + runs[-1][1]:
        runs[-1][1] += 1
    else:
        runs.append([x, 1])
per = defaultdict(list)
for s, length in runs:
    f, r = divmod(s, fc); line, col = divmod(r, lc)
    per[f].append((line, col, length, [f"{int(ref.samples[s+i]):#04x}>{int(uo[s+i]):#04x}" for i in range(length)]))
for f in sorted(per):
    lines = sorted({p[0] for p in per[f]})
    print(f"frame {f}: {sum(p[2] for p in per[f])} clocks, lines {lines[0]}-{lines[-1]}")
    for p in per[f]:
        if p[0] == lines[0]:
            print(f"   line {p[0]} col {p[1]} len {p[2]} {p[3]}")
