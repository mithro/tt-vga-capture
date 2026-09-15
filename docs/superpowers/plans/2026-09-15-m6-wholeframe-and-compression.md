# Milestone 6: whole-frame capture and compression — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture at the project's real clock rather than a slowed one, by buffering whole frames (or line windows) in the microcontroller's SRAM and sending them between frames, and by compressing the sample stream on the board. The target is a picture of a project running at its design clock, which slow-clock streaming cannot give.

**Architecture:** Three board-side capture programs sharing one prelude and one host protocol. `capture_rp2.py` (Milestone 3) streams continuously at a reduced clock. `frame_rp2.py` buffers one frame, or as much of one as fits, into SRAM triggered on vsync, then sends it as `FRAM` chunks while skipping the frames that elapse during the send. `window_rp2.py` captures a line range per frame and walks the window across successive frames, reassembling a full picture over several frames for content that repeats. A fourth strand, run-length encoding on the board, cuts the bytes per frame enough that the continuous mode reaches a higher clock. The host side already understands `FRAM` and `RLE` chunks and reassembles windows with a coverage map, so most of this milestone is board-side plus measurement.

**Tech Stack:** MicroPython on RP2040 and RP2350, `rp2.PIO`/`rp2.DMA`, the `ttcap` package and `vgacap` stream and frame libraries, the Welland boards.

**Spec:** `docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md` §5.3 (capture modes), §5.1 (`FRAM`, `RLE`), §8. Measurements that bound this milestone: `docs/research/2026-09-15-usb-cdc-throughput.md` (USB link ~150 KB/s on RP2040, ~650-740 KB/s on RP2350) and `docs/research/2026-09-15-micropython-capture-rate.md` (clean continuous clocks 60 kHz and 750 kHz).

## Global Constraints

- Apache-2.0; SPDX headers; Python via `uv`; MicroPython scripts free of host-only syntax and minified under 10 KB before upload (the `mp.minify` machinery from Milestone 3).
- Board memory, measured on 2026-09-15: RP2350 boards report about 397 KB free at capture time; RP2040 boards about 83 KB. A 640x480 frame including blanking is 420,000 samples: one byte each on RP2350 (fits), two bytes each on RP2040 (does not, by a wide margin).
- Every board-side rule learned in Milestone 3 still applies and is enforced by the existing tests: absolute GPIO numbers for `wait` and `in_base`, PIO0 never has its programs removed, the clock pad is never reconfigured, hard IRQ handlers are module-level with precomputed addresses, stopping is cooperative, and the uploaded script must fit the heap.
- Correctness is judged by the calibration designs, not by eye: a whole-frame capture of `tt_um_vgacal_counter` at its design clock must match the reference render for the counter value in the picture, and `tt_um_vgacal_prbs` must match with zero wrong pixels.
- Hardware runs are the controller's; sub-agents deliver code plus host tests against fakes.

## Task 1: share the board-side prelude

`python/ttcap/mp/prelude.py` holds what every capture program needs: the CFG contract, register arithmetic, `set_gpio_base`, `init_input_pins`, `make_sampler`, the chunk writers, the cooperative stop and the teardown. `mp.build(cfg, *names)` concatenates the prelude with one program body (concatenation, not import: the board has no package path for these). `capture_rp2.py` becomes a body using the prelude with no behaviour change, proven by asserting its minified output still passes every existing test and that a hardware capture is byte-identical in structure. `CaptureRequest` gains `script` so the host can choose the program.

## Task 2: whole-frame capture (`frame_rp2.py`)

Trigger on the vsync edge, DMA into one large buffer sized by the configured maximum (`frame_words`), stop at the next vsync edge or when the buffer is full, then emit the samples as one or more `FRAM` chunks carrying the frame counter, first line, line count and clocks per line, and skip whole frames while sending. On RP2040 boards, where a frame does not fit, capture the largest whole number of lines that does and report it: the host's coverage map then completes the picture from successive frames, which is Task 3's mechanism. The frame counter increments per captured frame so the host can tell a reassembled picture from a torn one. Host side: `ttcap capture --mode frame` selects it; `run_capture` already counts `FRAM` chunks after Milestone 5 Task 2.

## Task 3: windowed capture (`window_rp2.py`)

Capture a line range per frame, advancing the range each frame until the picture is covered, with the range and stride in CFG. Emit `FRAM` chunks with the correct `first_line` so the existing coverage logic assembles them. This is the mode that gives a full-rate picture of a static or frame-periodic design on an RP2040 board. A calibration design proves it: `tt_um_vgacal_grid` at 25 MHz reassembled from windows must be pixel-exact, and `tt_um_vgacal_counter` must show a single counter value per assembled picture or be reported as torn.

## Task 4: run-length encoding on the board

Emit `RLE` chunks instead of `RAW` when the content compresses: count runs in the DMA buffer on the CPU and write pairs. Measure honestly, on real content: the fpga-1 bars capture gzips to 0.6% of its size, so the ceiling is high, but MicroPython's per-sample loop is slow. Measure the achievable sample rate with RLE against the plain 750 kHz on RP2350 and 60 kHz on RP2040, and keep the mode only if it wins. Record the measurement either way; a negative result is a result. If the CPU loop is the limit, note what a PIO-side run counter would need (a second state machine comparing consecutive samples) as Milestone 7 work rather than attempting it here.

## Task 5: measurement and results

For each mode and board: the maximum clean project clock, the frames per second, the reassembly latency for windowed mode, and a pixel-exact calibration capture at the design clock (25.175 MHz for the standard modes). Write `docs/research/` on what each mode costs and when to choose it, and `docs/results/` with the pictures, including the first capture of a project running at its real clock.
