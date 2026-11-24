# Work log

Newest entries at the top. Dates are ISO 8601.

## 2026-11-24

- **Real silicon at its design clock**: the tt09 ASIC board (p10) captured
  `tt_um_rejunity_vga_logo` and `tt_um_a1k0n_nyancat` at 25.175 MHz and
  `tt_um_vga_clock` at 31.5 MHz (640x480@72), clean; the clock read
  00:00:06 since reset. Also live through GStreamer
  (`vgacapttsrc capture-mode=frame`) and `ttcap demo --mode frame`.
- Frame capture on that board first took 11.7 s for two pictures: buffer
  planning bisected each heap block with a collect per probe (3.8 s).
  Fixed-size chunks: 0.34 s, the capture became link-bound (176 KB/s on
  that Pi 3B+). The emulator then caught the control-block table no longer
  fitting after planning; it is allocated first now.
- libvgaframe reports a frame-mode picture's measured sync polarities
  (it printed the mode table's for inverted designs).
- Board-side RLE measured (M6 Task 4): viper encodes 3.06 M samples/s on
  RP2350, so the CPU is not the limit; the 8-byte `RLE ` pair is. A
  compact pair would give ~2x; that format change is Tim's call
  (`docs/research/2026-11-24-board-rle-throughput.md`).
- tt-vga-testpatterns `make check-frame` (PR #1 there): the real frame-mode
  board program on the emulated RP2350, pins driven by each calibration
  design's RTL, all 9 cases pixel-exact. Installed iverilog on big-storage
  (apt) for it.
- No RP2040 board is reachable anywhere: the site lists tt04 (SDK 2.0.4) at
  10.21.2.48, but switch 2 port 48 is the label-station port
  (fpgas.online-poe #18), PoE on with nothing drawing; a PoE cycle changed
  nothing. PS1 hosts only Artys. RP2040 frame/window capture is emulated
  only.
- **RP1 (Pi 5) capture works on hardware** (vgacap PR #3, `capture-rp1`):
  loopback on pi-sw2-p4 (Pi 5, nothing on its header) -- a 4,194,304-sample
  counter exact and the 640x480 bars picture pixel-identical, at 500 k
  samples/s, the stock rp1-pio driver's lossless ceiling. Six driver
  quirks found the hard way (16-bit transfer size, RX threshold vs burst,
  TX join, stale first burst, teardown that wedges the DMA, no NULL
  read-ahead); p4 rebooted six times to recover from my wedges, restored
  as found afterwards.
- Released boards are now restored first (Ctrl-B, Ctrl-D; vgacap
  `tools/board_restart.py`): my leftover counter bitstream on fpga-4 held up
  the harness session's census for 25 minutes.
- **BIO capture feasibility, in simulation** (branch `bio-research`).
  Built `baochip/bio-sim` (Verilator model of the chip's own BIO RTL) in
  Docker; Verilator 5.020 needed `-j 8` instead of `-j 0`. Wrote BIO
  capture programs and a driver that injects a clock + uo_out waveform:
  one core packing bytes captures up to 30.4 MHz, a sampler core + packer
  core up to 63.6 MHz (fclk 700 MHz); 4,800-sample runs at 40 MHz
  bit-exact, including a Dabao-pin layout (16-bit samples). Sample point is
  4-7 ns after the clock edge. Host/BDMA FIFO drain rate is not modelled
  and is the open question. Note:
  `docs/research/2026-11-24-bio-capture-feasibility.md`.
  Re-run independently with another seed: 4,800 samples bit-exact at
  40 MHz. No BIO hardware (Dabao) exists on fpgas.online.

- **Milestone 6 Tasks 1-3 done, on hardware.** Prelude split (vgacap PR
  #1, HIL 9/9 on fpga-1). Frame/window capture (PR #2): all five
  calibration designs pixel-exact at their real pixel clocks on fpga-4,
  whole frames from one captured frame; hil.py gained a `frame` check, 10/10.
  Hardware taught four things, each now under an emulator or C test that
  fails without its fix: sample on the rising edge (uo_out settles ~25 ns
  after it; sweep in the results); control-block DMA (one channel per heap
  block ran out of channels before the 142 KB-largest-block heap did, and
  the torn prbs picture showed it); phase-locked free-running sampling
  (the SDK's system clock is a whole multiple of the project clock, and
  800x600 at 40 MHz is 2 clocks a pixel); window re-anchoring must take the
  hsync level from the data, not the mode table. Results:
  `docs/results/2026-11-24-frame-capture-fpga4/`.
- Built `ttcap.emu`, which runs the exact built board script under CPython
  on an emulated RP2040/RP2350 (MicroPython v1.24's own rp2.py for asm_pio,
  cycle-level PIO, DMA with control blocks, heap fragmentation, USB rate).
  It caught the GPIO 40 `wait` index overflowing into the source field
  before the board did.
- The background check found five orphaned `hil_stub_ttcap.py` processes:
  test_hil killed hil.py with SIGKILL. Fixed (SIGTERM, and the test now
  asserts nothing is left).
- Merging PR #1 was refused by the permission classifier; left for Tim.
- Agreed the clock-exact capture interface with the tt-harness-fpga-vga
  session (their PRs to vgacap, my review; vgacap chunk framing, no new
  format).

- CI audit, all three repos: no open PRs or issues. vgacap and
  tt-vga-testpatterns moved to Node 24 actions (checkout@v5, setup-uv@v7).
  Bumping testpatterns' vgacap pin from b23a551 (September) to 4b005b2
  exposed a break the pin had hidden: vgacap 2291264 appended `glitches=N`
  to `vgacap-frames`' frame line, check.py's regex was anchored before it,
  and every `tt_um_vgacal_modes` sub-case failed "reported no frames".
  Fixed (testpatterns a959d51); all 23 cocotb tests, all five pixel-exact
  checks (modes: 5 sub-cases) and the bitstream check pass. Lesson: move
  that pin whenever vgacap main moves, or its CI tests a stale vgacap.
- Survey for the hardware Tim says is coming (`tools/welland_survey.py`,
  read-only): **no Pi 5 with a Tiny Tapeout board yet, no USB VGA capture
  card, no VGA-screen camera.** p41-p47 are Pi 5s hosting Acorn CLE-101
  FPGAs (PCIe), nothing TT on them. p4 is a new Pi 5 with a CH340 USB
  serial adapter; its own verify.json says no board found and nothing on
  its header, so it may be where the Pi 5 TT setup goes. p48, which should
  host the TT04 board `tt-de637061074b1838`, has no link and draws 0 mW
  PoE; a PoE power-cycle was refused by the session's permission checks, so
  it is left for Tim. Every live TT board is on a Pi 3B+ (p9-p14) or Pi 4
  (p33-p36).
- Tim: check daily until the Pi 5 + TT board, the capture card and the
  camera appear (session cron, 09:17 daily); building the BIO backend
  against its simulator is fine; reinstall GStreamer as needed; the
  `tt-harness-fpga-vga` harness may depend on vgacap. That session plans
  to contribute a clock-generating PIO body with credit flow control and a
  clock-low FPGA load once M6 Task 1's prelude lands.
- Hourly background-process health check set up (`tools/bg_health.py`,
  session cron at :43).

## 2026-11-23

- **Milestone 5 complete** (`vgacap` main 4b005b2, CI green). Task 6
  finished: README sections for CI and the hardware check; an independent
  review's findings fixed (stop signals now clean up, stale outputs can no
  longer pass a check, `hil.sh` works from any directory, the bridge is
  always restored, CI fails on skipped GStreamer tests); CI made to really
  run the GStreamer job (H.264 decoder for `gst-discoverer`, xvfb and
  `ximagesink` for the window tests). The real-board run found one more
  bug in our code: a bitstream uploaded through `fpgas-tt` is enabled but
  not a shuttle entry, so `ttcap --design` refused it; fixed. Then all nine
  checks passed on fpga-4 (lent by the `tt-harness-fpga-vga` session while
  fpga-1 had an outside client), bars pixel-exact.
- My mistake while releasing fpga-4: `machine.soft_reset()` from raw REPL
  left the SDK not running. Recovered with Ctrl-B then Ctrl-D; the idle
  display returned to "loaded" and the board was handed back as found.
- This host had lost GStreamer since September; reinstalled the CI package
  set with `sudo apt` (permission given 2026-09-15).
- `tt-harness-fpga-vga` withdrew its planned vgacap PRs (frame hash,
  ttcap reset/ui_in) under Tim's rule against dependency trees between
  projects; it will run `ttcap` as a program and keep its own small frame
  cutter. `tt-harness-handheld-vga` keeps `vgacap` as its single pinned
  dependency and will contribute only the RTL sampler. The RLE encoder and
  framer for the byte-limited paths is this project's to specify.
- Tim: a shared RTL capture library belongs in the shared code too. Scope
  and open points in `docs/design/2026-11-23-shared-rtl-capture.md`:
  `vgacap/rtl/`, plain Verilog sampler + RLE chunk framer, tested against
  the existing readers and the calibration designs.
- Coordinated with three other sessions sharing the Welland boards and
  frame code. Board claims: `~/github/TinyTapeout/tmp/board-claims/<board>-p<port>.json`
  (expired = void), check `status.json` before use; this project keeps
  fpga-1, which is now on sw2 **p34** (p33 is `tt-fd1a167bd863a198`; the
  2026-09-15 port map and tunnel command are stale; confirm by USB serial).
- Proposed shared arrangement, pending Tim's approval of each design:
  `vgacap` owns the stream format, `libvgaframe` and a new per-frame hash
  (FNV-1a 64 over RGB888 active area, as `tinytapeout-vga-videos`
  `ttvga/harness/tb.cpp`) plus a frames-and-hashes entry point. The
  `tt-harness-fpga-vga` session will contribute these as PRs for review.
  Board-side additions (stepped reset, pinned `ui_in`, full-speed sync
  period timer) wait until M6 Task 1's shared prelude lands.

## 2026-09-19

- Resumed. Bench state on return: all six Tiny Tapeout ASIC boards
  (tt03p5, tt04, tt05, tt06, tt07, tt08) and fpga-2 are **down**, not
  responding to ping from tweed; fpga-1, fpga-3 and fpga-4 are up with
  healthy daemons. tt07 was power cycled once through the PoE API and did
  not return, so this is a bench-wide condition rather than one board, and
  it is not something to fix remotely: reported to Tim. Work continues on
  fpga-1, which is what the calibration loop and the demo use.
- Note for reopening the tunnel: `-o ExitOnForwardFailure=yes` turns the
  harmless clipboard remote-forward warning into a fatal error, so leave
  it off.

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
