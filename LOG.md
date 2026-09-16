# Work log

Newest entries at the top. Dates are ISO 8601.

## 2026-09-17

- Weekly usage limit reached; the session pauses until 2026-09-19. State
  left safe and recoverable: all three repositories clean and pushed
  (`tt-vga-capture` 333889e, `vgacap` 375e368, `tt-vga-testpatterns`
  2473da6), no capture process running on either board and both
  `fpgas-tt` daemons active, so the shared hardware is free for others.
  The SSH tunnel to the Welland daemons has dropped and must be reopened
  on resumption.
- Outstanding when work resumes, in order: M5 Task 6 (CI covering the
  GStreamer plugin, plus `tools/hil.sh` for the checks only hardware can
  settle) — dispatched but stopped before it made any change, so nothing
  is half-done; then Milestone 6, whose plan is written
  (`docs/superpowers/plans/2026-09-15-m6-wholeframe-and-compression.md`).

## 2026-09-16

- **Milestone 5 complete** (`vgacap` main 375e368). `ttcap demo` merged
  after four fix rounds and re-run from main against fpga-1: 51 frames, a
  video file, the mode measured from the signal. The review loop earned
  its keep here: a `--help` crash 380 passing tests never hit, orphaned
  processes that could hold a shared board indefinitely, a summary that
  reported success having written nothing, and then the correction of that
  fix when it began reporting failure for runs that had worked. The last
  one is the lesson: an instruction to stop lying in one direction
  produced a lie in the other, and only running the unusual shapes
  (window-only, a short browser-only run) exposed it.
- Reviews and the SDD ledger for M5 archived under `docs/reviews/`.

## 2026-09-15

- **The demo runs.** One command against fpga-1 through the bridge:
  51 PNG frames, a 640x480 video file at the requested 5 fps, a live
  browser stream that served 32 JPEG frames, and the detected mode
  reported from the signal rather than echoed from configuration. Frame 25
  is pixel-identical to the calibration reference
  (`docs/results/2026-09-15-demo-fpga1/`). `ttcap demo --help` crashed on
  first use (argparse interpolating an unescaped `%04d` in a help string,
  a path 380 passing tests never exercised); fixed, with a test that now
  exercises `--help` for every subcommand automatically.
- **A GStreamer pipeline can now capture a Tiny Tapeout board directly.**
  `vgacapttsrc ! vgadecode ! ...` against fpga-1 produces frames
  pixel-identical to the calibration reference, and the `vgacapbin` URI
  form writes a video file carrying the project's own time base. Two fix
  rounds were needed: a teardown that could hang when a descendant
  outlived its parent, **arbitrary command execution through a URI query**
  (which would have become remote code execution once the browser view
  accepted URIs), and a stop signal that could reach a recycled process
  group. All three were found by review, two of them reproduced with
  strace, and each fix is pinned by a test that fails when reverted.
- M5 Tasks 2 and 3 merged. The GStreamer path works end to end on real
  hardware data: a capture of the FPGA emulation board decodes
  pixel-identically to the calibration reference through
  `filesrc ! vgadecode ! pngenc`, and encodes to a Matroska file whose
  duration (9.24 s) and frame rate (25/21) are the project's own time
  base rather than wall clock. Streaming to stdout sustained 730,714
  samples/s at the board's maximum clean clock with no overruns, and a
  consumer that stops reading now ends the capture cooperatively in about
  a second. Reviews caught two defects testing had not: timestamps that
  ran backwards on a mid-stream clock change (which would have corrupted
  the video file) and a stop-byte race whose commit had no coverage.
- M5 Task 1 merged: the tt08 `tt_um_rejunity_vga_logo` capture that used to
  reconstruct nothing now yields the Tiny Tapeout logo with 19 spurious
  sync pulses rejected and counted
  (`docs/results/2026-09-15-tt08-tiny-logo-glitch-tolerance/`), and a
  capture starting mid-frame no longer loses a frame. M5 Task 2 (streaming
  capture API for the GStreamer source) is in progress.
- **Milestone 4 complete.** All five calibration designs captured from
  fpga-1 and compared pixel-exactly: bars, grid, counter (five consecutive
  frames, counters 4 to 8, no drops or reordering), prbs (pseudo-random
  pixels, no redundancy to hide an error) and modes, which the board
  happened to drive at 800x600@60 with positive syncs and which the
  reconstruction detected unaided, matching all 480,000 pixels.
- **The calibration loop closed.** `tt_um_vgacal_bars` and
  `tt_um_vgacal_grid` were synthesised to iCE40UP5K bitstreams, uploaded to
  fpga-1 through the daemon API, captured at a 500 kHz project clock and
  reconstructed: all 307,200 pixels of each frame identical to the
  reference renderer, zero overruns, ten frames per 10 s capture
  (`docs/results/2026-09-15-calibration-loop-fpga1/`). This validates the
  capture path itself rather than agreement with someone else's design.
  M4 Tasks 3-4 merged beforehand (modes design, build flow, five
  bitstreams, CI); M5 Task 1 (learner robustness) is in a fix round.
- **Milestone 3 complete.** `vgacap` main b23a551: `ttcap` (board
  profiles, raw-REPL link with length-driven chunk reads, throughput and
  capture scripts, `ttcap probe/throughput/capture/png`), hardware-proven
  on RP2350 (fpga-1) and RP2040 (tt07, tt08) boards over the bridge and
  over direct serial on the Pis; 260 Python tests, warning-free. Final
  review's M5/M6 recommendations (streaming capture API, script prelude,
  FRAM handling, a host harness that executes the board script's main)
  are in the M5 plan. All three Pi checkouts updated.
- M4 Task 2 merged: `counter` and `prbs` designs; the check tool decodes
  the in-picture frame counter and verifies consecutive frames (default
  run now reconstructs three frames, counters 2, 3, 4). M4 Tasks 3-4
  (modes design, iCE40 builds, CI) dispatched. M3 final fix wave passed
  its hardware checks (PIO0 refusal, fpga-1, tt07) and is in re-review.
- PIO program leak fixed and merged (a board with full PIO memory
  recovered without a power cycle); both Pi checkouts updated. M3 final
  whole-milestone review dispatched.
- Clock sweep with `ttcap capture` over direct serial: RP2350 clean up to
  750 kHz (727 k samples/s), overruns from 1 MHz; RP2040 clean at 60 kHz,
  two overruns at 75 kHz. The 100 kHz run on tt07 failed with ENOMEM: the
  capture script never removes its PIO program, so about ten runs fill
  the block's instruction memory; a fix (remove in finally, defensive
  removal before adding, coalesced overrun lines) is in progress.
  `docs/research/2026-09-15-micropython-capture-rate.md`.
- M3 Task 4 merged after four hardware-driven fix rounds (cooperative
  stop byte, uo_out-only pad init, byte/frame limits, CLI error handling,
  minified upload, heap cleanup). Production path proven: `ttcap capture`
  on the tt07 Pi over direct serial with `--profile auto`, 1.68 M samples
  at 59 k/s, zero overruns, daemon restored
  (`docs/results/2026-09-15-ttcap-capture-serial-tt07/`). M4 Task 1
  merged (VESA-correct generator, bars + grid pixel-exact with the bar
  boundary at column 10); M4 Task 2 (counter, prbs) in progress.
- M4 Task 1 review settled the timing question: `libvgaframe` is
  VESA-correct; the fpgas.online demo / VGA playground `hvsync_generator`
  has a one-clock, one-line phase error, so the demo's picture (hardware
  and simulation alike) sits one pixel left and one line up of its intended
  coordinates. My earlier "pixel-exact" claims for the demo were true only
  at the sampled bar centres; both result notes now carry a correction.
  Ruling: the calibration designs get a VESA-correct shared generator and
  no per-design corrections. Task 4 hit RP2040 heap pressure at script
  load (25 KB script vs ~80 KB free heap; two board halts): round 3 shrinks
  the uploaded script and cleans the namespace before each run.
- **First silicon picture.** tt07 (RP2040 board, firmware v1.24/2.0.4)
  running `tt_um_rejunity_vga` at 60 kHz through the same minimal script
  with the 12-bit RP2040 layout: 1.47 M samples, zero overruns, one
  complete 640x480@60 frame with positive syncs detected automatically
  (`docs/results/2026-09-15-first-silicon-capture-tt07-tt_um_rejunity_vga/`).
  Board-side rate 114 KB/s at two bytes per sample, so ~57 k samples/s;
  60 kHz is the ceiling for this path on RP2040 boards. Cross-check
  against a simulation of the project's own Verilog is a follow-up.
- **First real picture.** fpga-1 (RP2350, stock firmware) running
  `tt_um_vga_pattern` at a 500 kHz project clock, captured with a minimal
  MicroPython PIO+DMA script through the debug bridge: 3.28 M samples,
  zero overruns, six complete 640x480@60 frames, pixel values matching the
  design (`docs/results/2026-09-15-first-capture-fpga1-tt_um_vga_pattern/`).
  Getting there took an afternoon of board experiments, all recorded in
  `docs/research/2026-09-15-rp2350-micropython-pio-findings.md`: the PIO
  base must be cleared and set for real, `in_base` and `wait gpio` are
  absolute GPIO numbers on this firmware, the clock pad must not be
  touched, hard IRQ handlers must be module-level. Two power cycles of
  fpga-1 were needed along the way. M3 Task 4 is in a fix round with the
  corrected rules.
- M3 Tasks 2-3 merged after a fix round that caught real problems before
  any hardware run: `rp2.asm_pio` clears globals (closures needed), the
  plan's SHIFT_RIGHT packing was wrong (ruled SHIFT_LEFT + first-sample-MSB),
  input pads must be initialised, DMA re-arm belongs in the IRQ handler,
  and my dispatch quoted wrong DMA register offsets (WRITE_ADDR +0x04,
  TRANS_COUNT +0x08; the implementer used the right ones).
- Measured USB CDC throughput on the boards: RP2040/MicroPython 1.24
  ~150 KB/s, RP2350/1.29-preview ~650-740 KB/s, identical through the
  bridge and direct serial; 32 KB blocks fail to allocate on the RP2040.
  First-capture clocks: ~60 kHz on tt07, ~500 kHz on fpga-1.
- M3 Task 4 (host capture flow) and M4 Task 1 (calibration designs
  scaffold) dispatched in parallel.
- **Milestone 2 complete.** `vgacap` main f83cc99: stream format v1 with
  reader resync after framing errors and full length validation,
  `libvgaframe` with per-chunk FRAM mode and a settled output API
  (stride, documented buffer lifetime, `vgaframe_reset`), tools, Python
  mirror and synthetic end-to-end tests. Final review and its SDD ledger
  archived under `docs/reviews/`. Measured on the host during review:
  ~70 Msample/s RAW decode + reconstruct, ~280 Msample/s RLE.
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
