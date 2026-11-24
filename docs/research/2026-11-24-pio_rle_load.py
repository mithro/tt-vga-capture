# SPDX-License-Identifier: Apache-2.0
"""PIO run-length encoding: what one frame of each calibration design costs.

Runs vgacap's `rle_rp2.make_rle()` on the cycle-level emulator (`ttcap.emu`)
for a whole 640x480@60 frame (800 x 525 = 420,000 project clocks) of each
tt_um_vgacal_* design, counts the words the state machine pushes in exactly
one frame, checks the expanded samples are an unbroken stretch of the
design's signal, and works out what that means for DMA, USB and RAM.

Run from vgacap's python/ directory (it needs vgacap's environment, its
emulator, and its tests/rle_pio.py helpers):

    cd ~/github/TinyTapeout/vgacap/python
    uv run python ~/github/TinyTapeout/tt-vga-capture/docs/research/2026-11-24-pio_rle_load.py

The reference pictures come from tt-vga-testpatterns' own tools/render.py
(--testpatterns, default ~/github/TinyTapeout/tt-vga-testpatterns), so the
counter and prbs frames are exactly what the RTL draws.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

HOME = pathlib.Path.home() / "github" / "TinyTapeout"
FRAME_CLOCKS = 800 * 525
SYSCLK = 150_000_000
PERIOD = 6  # locked, masked: 25 MHz at 150 MHz
USB_BYTES_S = 700_000  # RP2350 CDC, 2026-09-15-usb-cdc-throughput.md
CPU_RLE_SAMPLES_S = 3_060_000  # viper encoder, 2026-11-24-board-rle-throughput.md


def leb128_len(n: np.ndarray) -> np.ndarray:
    out = np.ones_like(n)
    m = n >> 7
    while m.any():
        out += m > 0
        m >>= 7
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--testpatterns", type=pathlib.Path, default=HOME / "tt-vga-testpatterns")
    ap.add_argument("--frame", type=lambda s: int(s, 0), default=0xA5,
                    help="frame counter for counter/prbs (default 0xA5)")
    a = ap.parse_args()

    sys.path.insert(0, str(pathlib.Path.cwd() / "tests"))
    sys.path.insert(0, str(a.testpatterns))
    from rle_pio import Run, expand_words, matches_signal  # noqa: E402
    from tools import render  # noqa: E402

    from vgacap.modes import MODES  # noqa: E402
    from vgacap.synth import frame_samples  # noqa: E402

    mode = MODES["640x480@60"]
    designs = {
        "bars": render.bars(),
        "grid": render.grid(),
        "counter": render.counter(a.frame),
        "prbs": render.prbs(a.frame),
    }
    print("design   changes  words/frame  of raw words  RLE B (8/pair)  packed B (4/pair)  "
          "compact B (u8+LEB128)  avg run  exact")
    rows = []
    for name, image in designs.items():
        uo = frame_samples(mode, image).tobytes()
        sig = np.frombuffer(uo, dtype=np.uint8)
        # Two frames of the same picture back to back: the emulator's
        # signal repeats, and one frame is counted from a mid-frame start.
        run = Run(uo, PERIOD, locked=True, masked=True, words=8 * FRAME_CLOCKS)
        run.advance(PERIOD * 1000)
        w0 = len(run.words())
        run.advance(PERIOD * FRAME_CLOCKS)
        words = run.words()
        per_frame = len(words) - w0
        run.advance(PERIOD * 1000)
        words = run.words()
        samples = expand_words(words)
        exact, _ = matches_signal(samples, uo)
        exact = exact and len(samples) > FRAME_CLOCKS and run.rxstall() == 0
        # The same count from the signal: runs in one cyclic frame.
        changes = int(np.count_nonzero(sig != np.roll(sig, 1)))
        ends = np.flatnonzero(sig != np.roll(sig, -1))
        runs = np.diff(np.concatenate(([ends[-1] - FRAME_CLOCKS], ends)))
        compact = int((1 + leb128_len(runs)).sum())
        raw_words = FRAME_CLOCKS // 4
        rows.append((name, changes, per_frame, compact))
        print("%-8s %7d  %11d  %11.1f%%  %14d  %17d  %21d  %7.1f  %s" % (
            name, changes, per_frame, 100.0 * per_frame / raw_words, 4 * per_frame,
            2 * per_frame, compact, FRAME_CLOCKS / changes, "yes" if exact else "NO"))

    print()
    print("At 25 MHz (59.5 frames/s), one frame = %d clocks:" % FRAME_CLOCKS)
    fps = 25_000_000 / FRAME_CLOCKS
    print("design   PIO words/s  sysclk/word  RLE MB/s  fastest clock the USB streams: "
          "RLE  compact  | samples/s at the link: RAW  CPU-RLE(8B)  PIO-RLE(8B)  PIO-compact")
    for name, changes, per_frame, compact in rows:
        words_s = per_frame * fps
        bytes_clk = 4 * per_frame / FRAME_CLOCKS
        compact_clk = compact / FRAME_CLOCKS
        raw = USB_BYTES_S
        cpu = 1 / (1 / CPU_RLE_SAMPLES_S + bytes_clk / USB_BYTES_S)  # encode, then send
        print("%-8s %11.3g  %11.1f  %8.2f  %31.3g  %7.3g  | %30.3g  %11.3g  %11.3g  %11.3g" % (
            name, words_s, SYSCLK / words_s, 4 * words_s / 1e6,
            USB_BYTES_S / bytes_clk, USB_BYTES_S / compact_clk,
            raw, cpu, USB_BYTES_S / bytes_clk, USB_BYTES_S / compact_clk))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
