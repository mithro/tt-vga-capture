"""Does a capture equal the reference shifted by s clocks (sample k == ref[k - s]) for small s?"""
import sys
from pathlib import Path
import numpy as np
from vgacap.stream import read_stream
from tthfv import compare, reference
from tthfv.board.capture_file import _to_uo_out
ref = compare.load_reference(reference.reference_dir(sys.argv[1], "fpga-4")).samples
for name in sys.argv[2:]:
    h, items = read_stream(Path(name).read_bytes())
    v = [i[1] for i in items if i[0] == "run"]; c = [i[2] for i in items if i[0] == "run"]
    uo = _to_uo_out(np.repeat(np.asarray(v, np.uint64), np.asarray(c, np.int64)), h.signal_map, h.sample_bits)
    out = []
    for s in range(0, 3):
        n = min(len(uo) - s, len(ref))
        d = int(np.count_nonzero(uo[s:s + n] != ref[:n]))
        out.append(f"shift {s}: {d} of {n} differ")
    print(Path(name).name, "; ".join(out))
