"""Compare a clocked capture, from clock 0, with each model's uo_out.bin dump."""
import sys
from pathlib import Path
import numpy as np
from vgacap.stream import read_stream
from tthfv.board.capture_file import _to_uo_out

cap_path = Path(sys.argv[1])
header, items = read_stream(cap_path.read_bytes())
vals = [i[1] for i in items if i[0] == "run"]; cnts = [i[2] for i in items if i[0] == "run"]
uo = _to_uo_out(np.repeat(np.asarray(vals, np.uint64), np.asarray(cnts, np.int64)), header.signal_map, header.sample_bits)
for d in sys.argv[2:]:
    dump = np.fromfile(Path(d) / "uo_out.bin", np.uint8)
    n = min(len(uo), len(dump))
    diff = np.nonzero(uo[:n] != dump[:n])[0]
    first = int(diff[0]) if len(diff) else None
    print(f"{Path(d).name}: dump {len(dump)} clocks, compared {n} from clock 0: {len(diff)} differ, first {first}")
