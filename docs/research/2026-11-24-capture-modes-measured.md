# Capture modes, measured: what each costs and when to choose it

Date: 2026-11-24. Milestone 6 Task 5. Every number below is measured on
real hardware, with its source under `docs/results/`. Untested bounds are
labelled as such.

## The modes

| mode | board / backend | project clock (clean, tested) | rate | pictures | evidence |
|---|---|---|---|---|---|
| slow-clock streaming | RP2040 (tt07, SDK 2.x) | 60 kHz | 59,047 samples/s, 0 overruns, 28 s | a 640x480@60 frame every ~7.1 s of capture | `2026-09-15-ttcap-capture-serial-tt07` |
| slow-clock streaming | RP2350 (fpga-4), bridge | 500 kHz | 487,399 samples/s, 0 overruns, 10 s | 11 frames from 10 s | `2026-11-23-hil-fpga4` |
| slow-clock streaming | RP2350 (fpga-4), direct serial | 750 kHz | 704,941 samples/s, 0 overruns, 4 s | 6 frames from 4 s | `2026-11-24-direct-serial-fpga4` |
| whole frame | RP2350 (fpga-4), 640x480@60 | 25 MHz (4 sysclk a clock) | link-bound, ~414 KB/s incl. setup | 3 pictures in 2.79 s (direct) | `2026-11-24-direct-serial-fpga4`, `2026-11-24-frame-capture-fpga4` |
| whole frame | RP2350 (fpga-4), 720x400@70 | 28.25 MHz (4 sysclk) | -- | exact | `2026-11-24-frame-capture-fpga4` (modes.log) |
| whole frame (two windows) | RP2350 (fpga-4), 800x600@60 | 40 MHz (2 sysclk, phase-locked) | -- | exact | same |
| whole frame | RP2350 ASIC (tt09), Pi 3B+ | 25.175 / 31.5 MHz | ~176-179 KB/s link | 2 pictures in 5.1-11.7 s; live demo ~0.4 pictures/s | `2026-11-24-frame-capture-fpga4` (tt09), `2026-11-24-direct-serial-fpga4` |
| windowed, 48 lines | RP2350 (fpga-4), 640x480@60 | 25 MHz | -- | one picture from 11 frames in 1.21-1.23 s, wall time from command to file | `2026-11-24-frame-capture-fpga4` (window.log) |
| RTL framer, one-shot RAM window | RP2350 + iCE40 (fpga-4), 16-bit sampler | 25 MHz | 65,536 consecutive clocks per window | -- (a test path, not a picture mode) | `2026-11-24-rtl-framer-fpga4` |
| RP1 PIO streaming | Pi 5 loopback (pi-sw2-p4) | 0.5 M samples/s | lossless | counter exact, bars pixel-identical | vgacap PR #3, LOG 2026-11-24 |

**Not measured on hardware**
- Whole-frame and windowed capture on an RP2040: emulated only, because no
  RP2040 Tiny Tapeout board is connected anywhere (survey of every Pi on
  2026-11-24).
- RP1 against a real Tiny Tapeout board: no Pi 5 is wired to one.
- BIO: simulator only.
- A higher clock than 40 MHz in frame mode: the phase-locked sampler needs
  at least 2 system clocks per project clock, so the bound is half the
  system clock the SDK sets. Untested above 40 MHz, and limited in practice
  by the design's own Fmax.

## What limits each mode

- **Streaming is the link, not the CPU.** The RP2350's USB CDC moved
  700–713 KB/s on fpga-4's Pi, through the bridge or direct, and 179 KB/s
  on the tt09 board's Pi 3B+ by either path (`2026-11-24-direct-serial-fpga4`).
  At one byte a sample, that caps the project clock at about 700 kHz there
  and about 175 kHz on the Pi 3B+. The RP2040's 12-bit samples and older
  firmware cap it at 60 kHz. The design runs slowed down, so nothing that
  depends on real time (the tt09 VGA clock, animation speed) is seen as it
  really is.
- **Whole frame is the heap, then the link.** 481 lines × 800 bytes is
  385 KB. The RP2350 holds it through control-block DMA over fragmented
  blocks; tt09's heap gave 434–451 lines, so one picture came from two
  frames, and ttcap says so. Each picture then costs its 385 KB on the
  link: about 0.55 s at 700 KB/s, or about 2.2 s at 179 KB/s. The design
  runs at its real clock, which is the point.
- **Windowed trades frames for memory.** 48-line windows need about 38 KB,
  so they fit an RP2040, and a picture takes 11 frames (about 0.18 s of
  video) plus the same 385 KB of transfer. The picture is exact only for
  content that repeats every frame; animated content tears, and ttcap
  prints a note saying so.
- **Compressed streaming** (`2026-11-24-board-rle-throughput.md`): CPU RLE
  in viper encodes 3.06 M samples/s, so the encoder isn't the limit, the
  8-byte `RLE ` pair is: +12% at best. A compact pair would give about 2x,
  and that is a format decision pending with Tim. PIO-side run counting is
  being researched under Milestone 8.

## When to choose which

1. **The design must run at its real clock** (timers, animation, anything
   checked against wall time): whole frame on an RP2350. Windowed if the
   heap won't hold a frame (RP2040) and the content is static.
2. **A continuous record is needed** (every frame, glitches between
   frames, long runs): streaming, with the design slowed to what the link
   carries. Own the serial device directly on the Pi when the bridge is
   shared, though it is not faster.
3. **Pixel-exact comparison against a reference** works in every mode. The
   calibration designs passed in all of them; only frame-to-frame content
   breaks windowed capture.
4. **Fastest pictures from fast content:** whole frame on the best-linked
   Pi, about 1 picture a second on fpga-4. A compact RLE chunk would
   roughly double it for compressible pictures.
