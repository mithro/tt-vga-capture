"""Where a clocked capture differs from the reference: clock, frame, line, column, the bits, the values."""
import sys
from pathlib import Path
import numpy as np
from vgacap.stream import read_stream
from tthfv import compare, reference
from tthfv.board.capture_file import _to_uo_out

key, path = sys.argv[1], Path(sys.argv[2])
header, items = read_stream(path.read_bytes())
vals = [i[1] for i in items if i[0] == "run"]; cnts = [i[2] for i in items if i[0] == "run"]
uo = _to_uo_out(np.repeat(np.asarray(vals, np.uint64), np.asarray(cnts, np.int64)), header.signal_map, header.sample_bits)
ref = compare.load_reference(reference.reference_dir(key, "fpga-4"))
fc = compare.frame_clocks(ref.meta); lc = ref.meta["line_clocks"]
n = min(len(uo), len(ref.samples))
d = np.nonzero(uo[:n] != ref.samples[:n])[0]
print(f"frame_clocks {fc} line_clocks {lc} compared {n} diffs {len(d)} reference frames {n / fc:.2f}")
xor = np.bitwise_or.reduce(uo[d] ^ ref.samples[d]) if len(d) else 0
print(f"bits differing (OR): {int(xor):#04x}")
prev = None
for c in d:
    c = int(c)
    f, r = divmod(c, fc); line, col = divmod(r, lc)
    if prev is None or c != prev + 1:
        print(f"clock {c}: frame {f} line {line} col {col}: ref {int(ref.samples[c]):#04x} cap {int(uo[c]):#04x}")
    prev = c
