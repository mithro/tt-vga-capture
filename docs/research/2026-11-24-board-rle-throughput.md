# Run-length encoding on the RP2350's CPU: is it worth it?

Date: 2026-11-24. Milestone 6 Task 4 asks for an honest measurement of
board-side RLE before building it into a capture program. Board: the tt09
ASIC board (`tt-3b0880b48ee5c388`, RP2350 at 133 MHz, MicroPython
670d775365). Script: `2026-11-24-rle_bench.py` beside this note.

## Measurement

One DMA buffer (4096 words = 16,384 one-byte samples) of 640x480@60 colour
bars with their syncs: 64 bars of 10 pixels, blanking and an hsync pulse per
800-sample line, 1,359 runs in the buffer (12 samples a run on average).
The same encoder three ways, output as `(u32 value, u32 run)` pairs -- the
existing `RLE ` chunk's layout:

| implementation | time per buffer | samples/s |
|---|---|---|
| plain MicroPython | 100.6 ms | 163 k |
| `@micropython.native` | 59.2 ms | 277 k |
| `@micropython.viper` (`ptr8` in, `ptr32` out) | **5.36 ms** | **3.06 M** |

All three produced the same 1,359 pairs. Output: 10,872 bytes for 16,384
bytes in.

## What it means for the two capture modes

The link carries ~700 KB/s on RP2350 (`2026-09-15-usb-cdc-throughput.md`).
The capture loop is single-threaded, so encode and send add.

**Streaming (`capture_rp2.py`)**, per 16,384-sample buffer:

| chunk | encode | send | total | samples/s |
|---|---|---|---|---|
| `RAW ` (today) | -- | 23.4 ms | 23.4 ms | 700 k |
| `RLE ` as specified (8 B a pair) | 5.4 ms | 15.5 ms | 20.9 ms | 784 k (+12%) |
| compact pair, ~3 B (u8 value + LEB128 run) | 5.4 ms | 5.8 ms | 11.2 ms | 1.46 M (2.1x) |

The CPU is not the limit: viper encodes four times faster than the link
moves raw samples. The *format* is: 8 bytes a pair spend most of what a
VGA picture offers. Busy content (`tt_um_vgacal_prbs`, runs of ~1) expands
under any RLE, so an encoder must fall back to `RAW ` per buffer whenever
RLE would be larger -- which costs the encode time and gains nothing, a
~23% slowdown on exactly the content that cannot afford it unless the
encoder gives up early (it can: stop as soon as the output passes the
input size).

**Frame mode (`frame_rp2.py`)**: a frame is 385 KB, ~0.55 s to send raw.
Encoding it takes ~126 ms with viper; with compact pairs a bars-like frame
would be ~100 KB, so ~0.27 s in total: about twice the picture rate. It
does nothing for the picture's *quality*, which is already exact.

## Recommendation, and the decision it needs

1. Not worth shipping with the existing `RLE ` chunk: +12% at best.
2. Worth doing with a compact chunk -- `u8 value` + LEB128 run, as the
   shared-RTL design note already leans -- for about 2x streaming rate on
   compressible content and about 2x frame rate, with a per-buffer
   fallback to `RAW `. That is a new chunk type in the vgacap format,
   which needs Tim's agreement and C and Python reader support; the
   encoder is a viper function of ~20 lines.
3. Whichever is chosen, the RTL RLE encoder (`vgacap/rtl/`) should emit
   the same chunk, so the format question is shared with that work.
