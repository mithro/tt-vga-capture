# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""BIO capture end to end in simulation: VGA signal in, picture out.

Drives bio-sim with WINDOW lines of a real 640x480@60 bars frame (starting a
line above the active area, as vgacap's frame mode does), keeps what the BIO
captured, wraps it in a vgacap FRAM chunk, reconstructs it with vgacap-frames
and compares the visible rows pixel for pixel with the source picture.

    uv run --no-project bio_picture.py --sim .../bio-sim --vgacap .../vgacap \\
        --work .../workdir [--lines 20] [--mode dual --edge fall --period 17.5]
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", required=True)
    ap.add_argument("--vgacap", required=True, type=Path, help="a built vgacap checkout")
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--lines", type=int, default=20)
    ap.add_argument("--mode", default="dual")
    ap.add_argument("--edge", default="fall")
    ap.add_argument("--period", default="17.5", help="aclk cycles a pixel (17.5 = 40 MHz at 700)")
    a = ap.parse_args()
    sys.path.insert(0, str(a.vgacap / "python"))
    import numpy as np
    from vgacap.modes import MODES
    from vgacap.ppm import read_ppm
    from vgacap.stream import TINYVGA_MAP, Header, Writer
    from vgacap.synth import bars, colour6_to_rgb, frame_samples

    mode = MODES["640x480@60"]
    first = mode.v_sync + mode.v_back - 1
    frame = frame_samples(mode, bars(640, 480)).tobytes()
    window = frame[first * mode.cpl:(first + a.lines) * mode.cpl]
    a.work.mkdir(parents=True, exist_ok=True)
    drive = a.work / "drive.bin"
    drive.write_bytes(window)
    got_path = a.work / "got.bin"
    run = subprocess.run(
        ["uv", "run", "--no-project", str(HERE / "run_capture_test.py"), "--sim", a.sim,
         "--logdir", str(a.work), "--mode", a.mode, "--edge", a.edge, "--period", a.period,
         "--tco", "2", "--clocks", str(len(window)), "--data-file", str(drive),
         "--save-samples", str(got_path),
         "--name", "bio-picture"], capture_output=True, text=True)
    result = json.loads(run.stdout.strip().splitlines()[-1])
    print("bio-sim:", json.dumps(result))
    got = got_path.read_bytes()
    offset = result.get("offset", 0)
    # The capture starts at the first edge the core waited for; the window's
    # first line is a blanking line, so dropping a few samples costs nothing
    # but the FRAM chunk must start on a line: pad back to the line start.
    samples = window[:offset] + got
    samples = samples[:len(window)]
    stream = a.work / "bio.vgacap"
    with open(stream, "wb") as fp:
        w = Writer(fp, Header(sample_bits=8, samples_per_word=4, flags=1, signal_map=TINYVGA_MAP,
                              mode=0, clock_hz=40_000_000, desc="bio-sim capture"))
        w.frame(0, first, a.lines, mode.cpl, list(samples))
    prefix = a.work / "f"
    for old in a.work.glob("f-*.ppm"):
        old.unlink()
    out = subprocess.run([str(a.vgacap / "build" / "vgacap-frames"), str(stream), str(prefix), "--partial"],
                         capture_output=True, text=True, check=True).stdout
    print(out.strip())
    ppm = sorted(a.work.glob("f-*.ppm"))[0]
    pic = read_ppm(ppm)
    want = colour6_to_rgb(bars(640, 480))
    rows = a.lines - 1  # the window's first line is blanking
    ok = pic.shape == want.shape and np.array_equal(pic[:rows], want[:rows])
    bad = int((pic[:rows] != want[:rows]).any(axis=2).sum()) if pic.shape == want.shape else -1
    print("visible rows 0..%d: %s (%d of %d pixels differ)" % (rows - 1, "pixel-exact" if ok else "DIFFERENT",
                                                              max(bad, 0), rows * 640))
    return 0 if ok and result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
