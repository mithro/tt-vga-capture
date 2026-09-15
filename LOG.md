# Work log

Newest entries at the top. Dates are ISO 8601.

## 2026-09-15

- Usage limit hit mid-afternoon: two sub-agents (the M2 final fix-wave
  re-review and the M3 Tasks 2-3 fix round) were killed before doing any
  work; both re-dispatched after the reset. Work already merged: M2 Tasks
  1-10; M3 Task 1. Pending: M2 final fix wave (resync, length validation,
  per-chunk FRAM mode, output API) awaiting re-review; M3 Tasks 2-3 fix
  round (asm_pio globals, shift-left packing ruling, pad init, IRQ-driven
  DMA re-arm, cleanup).
- Lesson: cloning `vgacap` on the tt07 Pi (Pi 3B+, armv7, 916 MB) and
  running `uv sync` started building numpy and Pillow from source, which
  made the Pi unresponsive (pings fine, SSH and the daemon hung). Power
  cycled it once through the PoE API (`tools/tt_power_cycle.py`, port 7
  on switch 2; back in 75 s), moved numpy/Pillow to an optional `synth`
  extra in `vgacap`, and documented `UV_NO_DEV=1` + `uv run --no-sync`
  for Pi use. A second accidental build (plain `uv run` re-syncs the dev
  group) was killed in time.
- M3 Tasks 2-3 delivered (throughput script, PIO+DMA capture script, host
  tests); review in progress. Ruling: the host reads the board's output
  length-driven by chunk headers because MicroPython's raw REPL ends
  stdout with an unescaped 0x04 that binary sample data can contain.
- M2 Task 9 (Python synthetic generator + end-to-end tests) merged after a
  fix round; its tests caught a real C bug (FRAM timing metadata ignored
  the resolved mode) which was fixed in the same task. M2 final
  whole-milestone review running. M3 Task 1 (`ttcap` board profiles and
  raw-REPL link) merged after a fix round; `uv run ttcap probe
  ws://127.0.0.1:18765/serial` reads the tt07 board's version and GPIO map
  through the debug bridge. M3 Tasks 2-3 (MicroPython throughput and
  PIO+DMA capture scripts) dispatched.
- M2 stream chain (Tasks 2-5) reviewed clean and merged into `vgacap` main.
  Frame chain (Tasks 6-8) review found a run-clip overflow, a crop-clamp
  underflow, FRAM reassembly never completing without a forced mode, and
  stale rows after a FRAM flush; all fixed with regression tests. Rulings:
  FRAM resolves its mode by clocks-per-line table match when nothing else
  is known; the continuous emit gate accepts a table-matched mode as
  sufficient evidence (`locked || mode || force_mode`). Parked: a stream
  of exactly two frame periods starting mid-frame can never yield a
  complete frame (needs a boundary plus a full frame); real captures run
  longer.
- First real-design cross-check: the fpgas.online `tt_um_vga_pattern`
  demo simulated with Icarus (3 frames, `tt-vga-testpatterns/tools/`)
  and wrapped with `vgacap-bin2stream` reconstructs pixel-exact through
  `vgacap-frames` (640x480@60 detected, locked, bars and gradient correct).
- Created `mithro/vgacap` (C skeleton: CMake, test harness, Python package,
  CI, the public `stream.h`) and `mithro/tt-vga-testpatterns` (README only)
  with the standard settings. Milestone 2 execution started with two
  sub-agents in parallel worktrees: stream chain (Tasks 2-5) and frame
  chain (Tasks 6-8) of the M2 plan.
- Created `mithro/tt-vga-capture` on GitHub with the standard settings
  (merge commits only, branch protection, secret scanning, tag ruleset
  `vXX.ZZZ`, `v0.0` on the first commit).
- Wrote the Milestone 2 plan (stream formats + reconstruction library).
  Decision: the stream reader emits `(value, run)` pairs for every chunk
  type, and `RAW` chunks store DMA words verbatim with the packing
  described in the header, so the MCU never repacks.
- Probed the Welland Pis: tt07 is on a Pi 3B+ (armv7l, 916 MB), fpga-1 on
  a Pi 4 (aarch64); both boards present (`2e8a:0005`), `fpgas-tt` active;
  python3 3.11, uv, gcc, gst-launch-1.0 and mpremote are installed on the
  Pis. SSH works as `pi` through tweed; `~/.ssh/config_extra` gained a
  `Host pi-sw2-p* 10.21.2.*` block.
- Brainstormed the project with Tim. Decisions recorded in
  `docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md`. Key points:
  three repos (`tt-vga-capture`, `vgacap`, `tt-vga-testpatterns`); all
  capture modes are wanted, simplest first; both external-clock and
  self-clocked sampling; multiple stream encodings allowed when justified;
  the Welland WebSocket bridge is for debugging only, real captures own
  the serial device on the Pi; whole-frame capture into RP2 SRAM is a
  first-class mode; never blame the hardware.
- Surveyed Welland: tt03p5-tt08 are RP2040 demo boards on switch 2 ports
  3-8; fpga-1..4 are RP2350 demo boards v3 with the FabricFox iCE40UP5K
  breakout on ports 33-36. `ten64` and `tweed` accept SSH; `tweed`'s host
  key had changed after its rebuild and was verified via `ten64` before
  updating `~/.ssh/known_hosts`. The Pis refused user `tim`.
- Extracted the RP2040 and RP2350 GPIO maps from the Tiny Tapeout
  MicroPython firmware (v2.0.4 `GPIOMapTT06`, v3.x `GPIOMapTTDBv3`): uo_out
  is not contiguous on RP2040 boards.
- Listed silicon-tested VGA projects on the Welland shuttles from the
  project-search database; candidates for the first capture: tt07 VGA
  Checkers, tt08 VGA Tiny Logo, tt08 Glyph Mode.
- Started local tooling: pico-sdk and oss-cad-suite into `~/tools/`.
