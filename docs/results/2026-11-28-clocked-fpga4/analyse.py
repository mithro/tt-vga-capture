"""Analyse 4e clocked captures: samples, closing records, and placement and comparison in the harness reference.

usage (from the tt-harness-fpga-vga checkout): uv run python analyse.py DESIGN_KEY FILE.vgacap ...

For each file: header mode and clock_hz, the TIME records, the sample count, and where the samples sit in the
design's fpga-4 reference (tthfv.compare.locate_capture over the first 840,000 reference clocks), then the
exact comparison over the overlap. A clocked run should place at the same reference clock every time.
Files whose samples are identical are grouped at the end.
"""

import hashlib
import sys
from pathlib import Path

import numpy as np
from vgacap.stream import read_stream

from tthfv import compare, reference
from tthfv.board.capture_file import _to_uo_out


def load(path: Path):
    header, items = read_stream(path.read_bytes())
    values, counts, times = [], [], []
    for item in items:
        if item[0] == "run":
            values.append(item[1])
            counts.append(item[2])
        elif item[0] == "time":
            times.append(item[4])
    expanded = np.repeat(np.asarray(values, np.uint64), np.asarray(counts, np.int64)) if values else np.zeros(0, np.uint64)
    return header, _to_uo_out(expanded, header.signal_map, header.sample_bits), times


def main() -> int:
    key = sys.argv[1]
    ref_dir = reference.reference_dir(key, "fpga-4")
    ref = compare.load_reference(ref_dir)
    digests: dict[str, list[str]] = {}
    for name in sys.argv[2:]:
        p = Path(name)
        header, uo, times = load(p)
        d = hashlib.sha256(uo.tobytes()).hexdigest()[:16]
        digests.setdefault(d, []).append(p.name)
        print(f"== {p.name}: mode {header.mode} clock_hz {header.clock_hz} samples {len(uo)} uo_out sha256 {d}")
        for t in times:
            print(f"   TIME {t}")
        if len(uo) < compare.ANCHOR_CLOCKS:
            print(f"   first samples: {[int(x) for x in uo[:16]]}; reference clocks 0..15: "
                  f"{[int(x) for x in ref.samples[:16]]}")
            continue
        loc = compare.locate_capture(uo, ref.samples, max_start_clocks=840000)
        if loc.start_clock is None:
            best = compare.best_partial_match(uo, ref.samples, max_start_clocks=840000)
            print(f"   no match; best partial {best}")
            continue
        c = compare.compare(uo, ref_dir, build_json=None, offset=-loc.start_clock, expect_key=None, overlap_only=True)
        print(f"   placed at reference clock {loc.start_clock} ({loc.best_candidates} tied, earliest "
              f"{loc.earliest_clock}); {c.verdict}: {c.compared_clocks} compared, first diff {c.first_diff_clock}, "
              f"diff clocks {c.diff_clocks}")
    print("== identical sample sets:")
    for d, names in digests.items():
        print(f"   {d}: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
