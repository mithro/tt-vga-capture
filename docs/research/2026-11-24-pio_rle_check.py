# SPDX-License-Identifier: Apache-2.0
"""Is a capture an unbroken stretch of a calibration design's signal?

    cd ~/github/TinyTapeout/vgacap/python
    uv run python ~/github/TinyTapeout/tt-vga-capture/docs/research/2026-11-24-pio_rle_check.py \
        capture.vgacap tt_um_vgacal_bars

Expands every `RAW `, `RLE ` and `FRAM` sample of a `.vgacap` stream (RP2350
8-bit uo_out samples, 640x480@60) and checks the whole stream, sample for
sample, against the design's own signal: the reference frames rendered by
tt-vga-testpatterns' tools/render.py and laid out with blanking and syncs by
vgacap.synth.frame_samples. Unlike vgacap-frames + compare_capture.py it
needs no complete frame, so it can judge a `--rle-oneshot` stretch shorter
than a frame. Designs that change every frame (counter, prbs) are tried
against every frame counter value: the stretch must match frames f, f+1,
... for some f. The prbs frames are made from one precomputed period of
the 16-bit LFSR, so all 256 are cheap.

Prints PASS (and where the stretch starts) or FAIL (and the first sample
that differs from the best candidate); exits 0 or 1. A stream with any
overrun or RXSTALL in its TIME chunks is a FAIL regardless.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

HOME = pathlib.Path.home() / "github" / "TinyTapeout"
CLOCKS = 800 * 525


def lfsr_cycle() -> np.ndarray:
    """The 16-bit Fibonacci LFSR of tt_um_vgacal_prbs (render._lfsr_pixels)
    from state 1 for one full period; index i holds the state after i
    steps."""
    states = np.empty(65535, dtype=np.uint16)
    s = 1
    for i in range(65535):
        states[i] = s
        bit = (s ^ (s >> 2) ^ (s >> 3) ^ (s >> 5)) & 1
        s = (s >> 1) | (bit << 15)
    if s != 1:
        raise SystemExit("the LFSR is not maximal-length; this fast path does not apply")
    return states


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stream", type=pathlib.Path)
    ap.add_argument("design", choices=["tt_um_vgacal_bars", "tt_um_vgacal_grid",
                                       "tt_um_vgacal_counter", "tt_um_vgacal_prbs"])
    ap.add_argument("--testpatterns", type=pathlib.Path, default=HOME / "tt-vga-testpatterns")
    a = ap.parse_args()
    sys.path.insert(0, str(a.testpatterns))
    from tools import render  # noqa: E402

    from vgacap.modes import MODES  # noqa: E402
    from vgacap.stream import read_stream  # noqa: E402
    from vgacap.synth import frame_samples  # noqa: E402

    mode = MODES["640x480@60"]
    header, items = read_stream(a.stream.read_bytes())
    runs = [(i[1], i[2]) for i in items if i[0] == "run"]
    msgs = [i[4] for i in items if i[0] == "time"]
    got = np.repeat(np.array([v for v, _ in runs], dtype=np.uint8),
                    np.array([r for _, r in runs], dtype=np.int64))
    print("%s: %d samples, sample_bits=%d; board said: %s" % (
        a.stream.name, len(got), header.sample_bits, " | ".join(msgs)))
    bad_time = [m for m in msgs if m == "overrun" or "rxstall=1" in m or m.startswith("error=")
                or (m.startswith("overruns=") and not m.startswith("overruns=0 "))]
    if header.sample_bits != 8 or not len(got):
        print("FAIL: needs a non-empty 8-bit (RP2350) stream")
        return 1

    short = a.design.removeprefix("tt_um_vgacal_")
    if short in ("bars", "grid"):
        candidates = {"fixed": lambda: frame_samples(mode, getattr(render, short)())}
        frames_needed = 1
    else:
        frames_needed = len(got) // CLOCKS + 2
        if short == "counter":
            def make(f):
                return lambda: np.concatenate([
                    frame_samples(mode, render.counter((f + k) & 0xFF)) for k in range(frames_needed)])
        else:
            cycle = lfsr_cycle()
            where = np.empty(65536, dtype=np.int64)
            where[cycle] = np.arange(65535)

            def prbs_image(f):
                img = np.zeros((480, 640), dtype=np.uint8)
                img[:8] = render._counter_strip(f, 640, 8)
                start = where[(0xACE1 ^ f) & 0xFFFF]
                idx = (start + np.arange(640 * 472)) % 65535
                img[8:] = (cycle[idx] & 0x3F).reshape(472, 640)
                return img

            # The fast path agrees with the renderer itself.
            assert np.array_equal(prbs_image(0x5A), render.prbs(0x5A))

            def make(f):
                return lambda: np.concatenate([
                    frame_samples(mode, prbs_image((f + k) & 0xFF)) for k in range(frames_needed)])
        candidates = {"frame %d" % f: make(f) for f in range(256)}

    head = got[: min(len(got), 20_000)].tobytes()
    best = None
    for label, build in candidates.items():
        ref = build()
        hay = np.tile(ref, len(got) // len(ref) + 2) if frames_needed == 1 else ref
        hay_b = hay.tobytes()
        start = hay_b.find(head)
        if start < 0:
            continue
        ref_part = hay[start : start + len(got)]
        if len(ref_part) == len(got) and np.array_equal(ref_part, got):
            if bad_time:
                print("FAIL: samples match %s, but the board reported %s" % (label, bad_time))
                return 1
            print("PASS: all %d samples are an unbroken stretch of %s, from clock %d "
                  "(line %d, x %d)" % (len(got), label, start, (start % CLOCKS) // 800, start % 800))
            return 0
        diff = int(np.flatnonzero(ref_part != got[: len(ref_part)])[0]) if len(ref_part) else 0
        if best is None or diff > best[1]:
            best = (label, diff, start)
    if best is None:
        print("FAIL: the first %d samples are not anywhere in the design's signal" % len(head))
    else:
        label, diff, start = best
        print("FAIL: best match %s from clock %d holds for %d samples; sample %d differs" % (
            label, start, diff, diff))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
