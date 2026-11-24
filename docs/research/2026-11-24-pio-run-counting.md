# Run-length encoding in the RP2's PIO: how fast, how exact, and is it worth it

Date: 2026-11-24. Milestone 8 asks whether the PIO itself can turn the
stream of `uo_out` samples (one per project clock) into (value, run) pairs,
so that only the changes cross the DMA and the USB link -- and up to what
project clock. This note answers with a working program
(`vgacap/python/ttcap/mp/rle_rp2.py`, branch `pio-rle`) proven cycle-exact on
the emulator (`ttcap.emu`, MicroPython v1.24's own `asm_pio`), and numbers
measured there. **No hardware was used**; the hardware check is at the end.

Labels: **MEASURED (emu)** came from the cycle-level emulator running the
real assembled program; **INFERRED** is arithmetic on those or on earlier
measurements, which are cited by file.

Beside this note: `2026-11-24-pio_rle_load.py` (the per-frame load table
below) and `2026-11-24-pio_rle_check.py` (checks any `.vgacap` capture,
sample for sample, against a calibration design's own signal).

## Summary

| | equal clock | changed clock | saturated (2^32) | shortest exact clock (system clocks) | at 150 MHz | at 133 MHz |
|---|---|---|---|---|---|---|
| locked, masked (RP2350) | 5 | 6 | 6 | **6** | **25.0 MHz** | 22.2 MHz |
| locked, OSR (any RP2) | 6 | 7 | 7 | 7 | 21.4 MHz | 19.0 MHz |
| edge-waiting, masked | 5 + 2 waits | 6 + 2 | 6 + 2 | 8 | 18.75 MHz | 16.6 MHz |
| edge-waiting, OSR | 6 + 2 | 7 + 2 | 7 + 2 | 9 | 16.7 MHz | 14.8 MHz |

(instructions per project clock; **MEASURED (emu)**: every row exact at its
shortest clock on whole frames and on worst-case signals, and the clock one
system clock shorter fails.)

- **Q1.** One state machine does it in 5 instructions on an unchanged clock
  and 6 on a change, so a phase-locked program padded to P = 6 system
  clocks is exact for *any* picture: 25 MHz at the RP2350's 150 MHz.
  "Masked" uses the RP2350's `SHIFTCTRL.IN_COUNT` so that one `mov y, pins`
  reads just `uo_out`; without it (RP2040) the sample goes through the OSR,
  one instruction more. Waiting for each clock edge instead costs two more.
  But the firmware runs a 25 MHz project clock from a 100 MHz system clock
  (4 a pixel, measured on fpga-4 in `frame_rp2.py`), where nothing fits:
  25 MHz needs the system clock at 150 MHz.
- **Q2.** Two words per change. Per 640x480 frame (420,000 clocks; raw is
  105,000 words): bars 63,540 words (61% of raw), grid 138,100 (132%),
  counter 5,780 (5.5%), prbs 597,966 (570%). At 25 MHz that is one word per
  40, 18, 436 and 4.2 system clocks; the RX FIFO (8 words joined) never
  stalls on the emulator with the DMA running, and on hardware stalls only
  if the DMA is held off for ~8 words -- 24 system clocks at the worst
  (a change every clock). The real limit is the link.
- **Q3.** `rle_rp2.py` streams the PIO's words as existing `RLE ` chunks,
  after a viper pass adds back one clock per run (see the program below);
  `ttcap capture --mode rle` runs it. On the emulator its chunks expand to
  exactly the samples `capture_rp2.py`'s `RAW ` chunks hold, and
  `vgacap-frames` makes pixel-exact pictures from them, RP2350 and RP2040.
  `--rle-oneshot` fills both buffers once at full speed: an unbroken
  stretch at 25 MHz that the link could never stream.
- **Q4.** With today's 8-byte pairs it beats RAW streaming only on coarse
  pictures: 1.16 M samples/s for bars (RAW: 0.70 M, CPU RLE: 0.84 M),
  12.7 M for counter; it loses on grid (0.53 M) and prbs (0.12 M). The
  8-byte pair is the problem, not the encoder: a compact pair (u8 value +
  LEB128 run) would give bars 4.6 M, grid 2.1 M and counter 47 M samples/s
  -- counter-like pictures streamed live at 25 MHz. The other big win is
  RAM: a whole RLE frame of bars is 254 KB (127 KB packed), counter 23 KB,
  which makes a whole-frame capture at the real clock fit where a raw frame
  (420 KB) does not.

## The program

`jmp x!=y` is the only comparison and `jmp y--` the only arithmetic, and
both want their operands in X and Y. So: X holds the run's value, Y is
scratch, and the run counter lives in the **ISR**, fetched inverted,
decremented and stored back inverted -- an increment. A `push` leaves the
ISR at 0, so a new run's counter costs nothing.

```
    wait clk_idle ; wait clk_act [delay]     sync to one edge (frame_rp2.py)
    mov y, pins                              the first sample
    in y, 32                                 v0 (autopush at 32); ISR = 0
    mov x, y
    jmp S              [P-4]
W:  mov isr, ~y        [P-5]                 counter += 1 (equal path)
S:  mov y, pins                              THE SAMPLE (wrap target)
    jmp x!=y chg
    mov y, ~isr
    jmp y--, W                               Y = 0 only when saturated
    push noblock                             2^32 samples: push the run,
    in x, 32           [P-6]                 the value again, count on (wrap)
chg: push noblock                            the run, minus one
    in y, 32                                 the new value; ISR = 0
    mov x, y
    jmp S              [P-6]
```

(17 instructions; the edge-waiting style puts the two waits after `S:` and
drops the padding; the OSR form replaces each `mov y, pins` by
`mov osr, pins` + `out y, n`, 19.) Paths from one sample to the next:

| path | instructions | form |
|---|---|---|
| equal | W S C L D | 5 |
| change | S C push in mov jmp | 6 |
| saturation | S C L D push in | 6 |
| entry | S0 in mov jmp | 4 |

In the **locked** style the delays pad every path to exactly P system
clocks, P = sysclk / project clock, so samples are exactly P apart and the
program relies on the SDK's whole-ratio clocking exactly as `frame_rp2.py`'s
phase-locked sampler does. P = 6 is the floor because the change and
saturation paths are 6 long (the `jmp S` back could be dropped by layout
only for one of the three paths that return to `S`: one falls through, one
wraps). The delay field holds 31, so locked works up to P = 35; slower
clocks use the **edge** style, which also needs no whole ratio.

The words come out as `v0, r0, v1, r1, ...` with each r the run minus one
(the changed sample is the new run's first and the loop never counts it).
So a DMA buffer of an even number of words is already an `RLE ` payload,
value then run, except for that one: the board adds it in viper
(`fix_runs`, one pass over the run words, cheap next to sending them). A
run word of all ones (2^32 samples) becomes 0 and is sent as two pairs of
2^31. A push to a full RX FIFO is `noblock`: the phase is kept and RXSTALL
is set (datasheet: "also set when a nonblocking PUSH to a full FIFO took
place"), and the summary reports it.

Why the mask matters: unmasked, `mov y, pins` reads all 32 pins from
`in_base` up, which on the RP2350 board wraps round to the project clock
pad (GPIO 16) and the `ui_in`/`uio` pads. **MEASURED (emu)**: without
`IN_COUNT` every value comes back above 0xFF. The OSR form takes exactly
the window through `out y, n` instead, which is also how the RP2040's
12-pin window (with `ui_in[0..3]` in the middle) is encoded.

## Exactness (Q1): how it was proven

All **MEASURED (emu)**, `vgacap/python/tests/test_rle_pio.py` and
`test_emu_rle.py` (47 tests): the assembled program runs on the emulated
state machine against a known signal; every pushed word is expanded back
into samples, which must be an unbroken stretch of the signal -- no clock
missed, doubled or altered -- and cover every clock that passed (all but
the open run).

- Whole frames (420,000 clocks) of bars and grid at P = 6, locked, masked;
  and in `2026-11-24-pio_rle_load.py` whole frames of bars, grid, counter
  and prbs (the real renderers), all exact, RXSTALL clear.
- Uniformly random bytes (a change on 255 of 256 clocks, worse than prbs)
  and a strict alternation (a change on every clock) in all four forms at
  their shortest clock, with both duty cycles an odd P allows.
- The design's clock-to-output delay 0..3 system clocks and sample delay
  0..1: one sample per clock either way.
- Locked at P = 7, 12 and 35 (the delay field's limit).
- A saturation in both styles: the counter poked to 2^32 - 16 at the top
  of the loop; the program pushes the run and the value again and counts
  on, and with the poked clocks taken out every sample is the signal again.
- Negative controls: a program padded for P on a clock of P - 1 fails; the
  edge style fails at each of the three clocks below its shortest.
- End to end, the built script on the emulated board: `RLE ` chunks at
  25 MHz/150 MHz decode to pixel-exact bars and grid pictures through
  `vgacap-frames`; at 500 kHz (edge style) they expand to exactly the
  samples `capture_rp2.py` captured as `RAW `; an RP2040 at 19 MHz/133 MHz
  (P = 7, OSR) gives pixel-exact pictures from its 12-bit window.

## Load per frame (Q2)

**MEASURED (emu)**, `2026-11-24-pio_rle_load.py`, locked, P = 6, one
640x480@60 frame counted from a mid-frame start (counter and prbs at frame
counter 0xA5); every row's samples exact:

| design | changes | words/frame | of raw (105,000 words) | `RLE ` bytes (8/pair) | packed 4/pair | compact (u8+LEB128) | mean run |
|---|---|---|---|---|---|---|---|
| bars | 31,770 | 63,540 | 60.5% | 254,160 | 127,080 | 63,585 | 13.2 |
| grid | 69,050 | 138,100 | 131.5% | 552,400 | 276,200 | 138,206 | 6.1 |
| counter | 2,890 | 5,780 | 5.5% | 23,120 | 11,560 | 6,225 | 145 |
| prbs | 298,983 | 597,966 | 569.5% | 2,391,864 | 1,195,932 | 598,019 | 1.4 |

At 25 MHz (59.5 frames/s) the state machine pushes 3.8 M (bars), 8.2 M
(grid), 0.34 M (counter) and 35.6 M (prbs) words a second: one word per
40, 18, 436 and 4.2 system clocks at 150 MHz. The fastest a change can
follow a change is the 6-cycle change path, two words in it, so the DMA
must sustain one word every 3 system clocks at worst. **INFERRED**: the RX
FIFO (joined, 8 words) then covers a DMA held off for 24 system clocks on
prbs-like content and hundreds on the others; with the ping-pong DMA
always armed it does not stall (the emulator's DMA is never held off, so
this is the one thing it cannot show). What does run out is everything
after the DMA: at 25 MHz even bars needs 15 MB/s of 8-byte pairs against
the link's 0.7 MB/s. Streaming at the real clock overruns at once
(**MEASURED (emu)**: reported as overruns, with `dropped_samples` a lower
bound of one sample per lost pair); `--rle-oneshot` is the way to see the
real clock.

## The board program (Q3)

`vgacap/python/ttcap/mp/rle_rp2.py`, a body after `prelude.py` like the
others; `ttcap capture --mode rle` (CaptureRequest script `rle_rp2.py`,
`ttcap.capture.rle_cfg()`), 9.9 KB built.

- Ping-pong DMA, hard-IRQ re-arm, cooperative stop, overrun and RXSTALL
  reporting: `capture_rp2.py`'s, repeated rather than shared.
- Output: `RLE ` chunks (pairs of u32 value + u32 run, `stream.h`) and
  `TIME` chunks: first `rle style=locked period=6 mask=1` (what it chose),
  last `overruns=N rxstall=R saturated=S sysclk_hz=F`. No new chunk type.
- `style` auto takes locked when sysclk / clock is whole (within 0.5%) and
  6..35 (7..35 unmasked), else edge when the shortest clock period is at
  least 8 (9) system clocks -- one cycle under the average for a
  fractional divider -- else it refuses with an `error=` TIME chunk.
- `mask` -1 picks the one-instruction sample on an RP2350 (it sets
  `IN_COUNT` through SHIFTCTRL's atomic SET alias after `StateMachine()`
  and reads it back), the OSR form on an RP2040; `--rle-mask 0/1` forces
  it.
- `--rle-oneshot`: both buffers once, back to back; B chains to
  `frame_rp2.py`'s stopper (one word into PIO CTRL's clear alias), so the
  state machine stops a few cycles after the last word and RXSTALL keeps
  its meaning. With `--buf-words 20000` (two 80 KB buffers, which fit
  fpga-1's measured heap) that is 20,000 pairs: **MEASURED (emu)** 267,927
  clocks of bars (64% of a frame) or 57,744 of prbs at 25 MHz, exact.
- Edge sampling defaults to `rising` with `--sample-delay 0`, frame
  capture's measured sample point.

The emulator gained what the program needs, each to the datasheet: `in`
from registers, `out`, pin reads that wrap round the window from `in_base`
(`mov` used to read from the window's base), `IN_COUNT`, the nonblocking
push's RXSTALL, and viper's `ptr32`.

## Limits and recommendation (Q4)

Streaming throughput, samples per second through a 0.7 MB/s link
(**INFERRED** from the table above and the earlier measurements:
`2026-09-15-usb-cdc-throughput.md`, `2026-11-24-board-rle-throughput.md`,
CPU encode and send in series):

| design | RAW | CPU RLE, 8 B | PIO RLE, 8 B | PIO RLE, compact |
|---|---|---|---|---|
| bars | 0.70 M | 0.84 M | 1.16 M | 4.6 M |
| grid | 0.70 M | 0.45 M | 0.53 M | 2.1 M |
| counter | 0.70 M | 2.47 M | 12.7 M | 47 M |
| prbs | 0.70 M | 0.12 M | 0.12 M | 0.49 M |

1. **PIO RLE beats or ties CPU RLE everywhere** -- it costs the CPU one cheap pass
   per pair instead of a 3.06 M samples/s encode -- and beats RAW on
   pictures whose mean run is above 8 clocks (bars, counter, most real
   designs' large flat areas), not on fine detail (grid's 6, prbs's 1.4).
   A capture should fall back to RAW per buffer when pairs outgrow samples,
   as the CPU RLE note already said; with PIO RLE that decision has to be
   made before the program starts, or by running both samplers on two
   state machines and DMA'ing whichever is smaller.
2. **The compact chunk is what makes it pay**: 4x on every row above, and
   counter-like pictures streamed live at 25 MHz. The PIO need not change:
   the board repacks pairs in its viper pass (per pair, not per sample).
   If a compact chunk is adopted, a 4-byte packed pair from the PIO
   (`run << 8 | value`) would halve the DMA and RAM too, at 2 more
   instructions on the change path (a 24-bit run needs its counter started
   at 0xFF000000 to saturate in time), i.e. P = 8: a trade for frame
   capture, not for streaming.
3. **Whole frames at the real clock in RAM.** A bars frame is 254 KB of
   8-byte pairs (127 KB packed, 64 KB compact), counter 23 KB: an RLE frame
   capture with `frame_rp2.py`'s control-block DMA over the heap's pieces
   would give whole pictures of most designs at 25 MHz on RP2350, and of
   counter-like ones even on an RP2040 -- with RAW windows as the fallback
   for grid- or prbs-like pictures, whose RLE is larger than raw.
4. **The system clock.** Every form needs P >= 6; the SDK's choice for
   25 MHz is 100 MHz (P = 4, measured on fpga-4), where no form fits. A
   25 MHz RLE capture needs the project clock made from 150 MHz / 6; that
   is a clocking decision for the firmware or the daemon, not for the PIO.
5. **Not worth it:** two state machines per stream. Sampling on one (`in
   pins, 8`, 1 instruction) and encoding on another fed by DMA frees the
   encoder from the clock phase but not from its 5-6 instructions a
   sample, so it is no faster; it would only let the RP2040 use the
   one-instruction sample. Unrolling (the program counter as a fine
   counter) shortens only the equal path, and the change path already sets
   the floor.

## Checking it on hardware

From `~/github/TinyTapeout/vgacap/.worktrees/pio-rle/python` (C built in
`../build`), board fpga-4 (RP2350), link `ws://127.0.0.1:18035/serial`,
design loaded by the daemon (add `--design tt_um_vgacal_...` if it should
be selected by `tt.shuttle` instead). `CHECK` is
`~/github/TinyTapeout/tt-vga-capture/docs/research/2026-11-24-pio_rle_check.py`.

1. Edge style, against RAW, at a clock the link carries:

   ```
   uv run ttcap capture ws://127.0.0.1:18035/serial --clock-hz 500000 --mode rle    --seconds 4 --out bars-rle-500k.vgacap
   uv run ttcap capture ws://127.0.0.1:18035/serial --clock-hz 500000 --mode stream --seconds 4 --out bars-raw-500k.vgacap
   uv run python $CHECK bars-rle-500k.vgacap tt_um_vgacal_bars
   uv run python $CHECK bars-raw-500k.vgacap tt_um_vgacal_bars
   ../build/vgacap-frames bars-rle-500k.vgacap f   # then compare_capture.py per frame
   ```

   prbs the same at `--clock-hz 50000 --seconds 25` (8.4 s a frame; its
   pairs need 285 KB/s there).
2. Locked style at the real clock, one shot:

   ```
   uv run ttcap capture ws://127.0.0.1:18035/serial --clock-hz 25000000 --mode rle --rle-oneshot --buf-words 20000 --out bars-rle-25m.vgacap
   uv run python $CHECK bars-rle-25m.vgacap tt_um_vgacal_bars
   ```

   and the same for prbs. If the first TIME message is `error=no exact rle
   style for sysclk 100000000 clock 25000000 ...`, the firmware chose 4x:
   retry at `--clock-hz 12500000` (P = 8 at 100 MHz) or `16666666` (P = 6).

**Pass:** the first TIME message names the style and period chosen
(`rle style=edge period=300 mask=1` at 500 kHz/150 MHz), the last says
`overruns=0 rxstall=0`, and `CHECK` prints `PASS` for every capture (it
checks every sample against the design's own frames, so it needs no
complete picture). On a `FAIL` with scattered bit errors at the real
clock, sweep `--sample-delay 0..P-1` and `--edge falling` as frame capture
did; `error=SHIFTCTRL.IN_COUNT did not take`, or values above 0xFF, means
rerunning with `--rle-mask 0` (then P >= 7).

**Not shown by the emulator** and so open until that run: `IN_COUNT` and
the SET alias on SHIFTCTRL (datasheet only); the viper pass and the
helper functions called inside the `asm_pio` body under real MicroPython;
DMA held off by the CPU and USB on the bus; the real input synchroniser
(a fixed delay on every pin, which moves the sample point but not the
spacing); any RP2040 hardware.
