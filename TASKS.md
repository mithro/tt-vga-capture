# Tasks

Status: `[ ]` todo, `[~]` in progress, `[x]` done, `[-]` dropped. Newest
decisions in `LOG.md`.

## Milestone 1: tracking repo, spec, plan, repos

- [x] Brainstorm with Tim and record decisions
- [x] Write the design spec and commit it
- [x] Write `docs/research/2026-09-15-welland-boards-and-gpio.md`
- [x] Create GitHub repos `tt-vga-capture`, `vgacap`, `tt-vga-testpatterns` with the standard settings
- [x] Write the Milestone 2 implementation plan (`docs/superpowers/plans/2026-09-15-m2-stream-and-frame.md`); later milestones get their own plans
- [x] SSH to the Welland Pis works as `pi` via tweed (`ssh pi-sw2-p33`)
- [x] Local tooling: pico-sdk and oss-cad-suite in `~/tools/`, GStreamer dev headers installed; cocotb still to add per repo

## Milestone 2: stream formats and reconstruction

- [x] `vgacap/stream`: chunk container, `VGCH` header, `RAW`, `RLE`, `FRAM`, `EVNT`, `TIME`; C encoder/decoder; Python reader/writer (merged 2026-09-15)
- [x] `vgacap/frame`: sync polarity + timing detection, mode table, active-area location, RGB24 framebuffer, frame callback (merged 2026-09-15)
- [x] Synthetic stream generator (C and Python) for every mode table entry and polarity (merged 2026-09-15)
- [x] Partial-frame accumulation for `FRAM` (merged 2026-09-15)
- [x] Unit tests and CI (8 C test binaries, 19 pytest cases, GitHub Actions green)
- [x] Final whole-milestone review: four Important findings fixed (reader resync + validation, per-chunk FRAM mode, output API stride/lifetime/reset); vgacap main f83cc99. Deferred minors listed in `docs/reviews/2026-09-15-m2-sdd-ledger.md`

## Milestone 3: first real picture from Welland (MicroPython PIO prototype)

Plan: `docs/superpowers/plans/2026-09-15-m3-micropython-capture.md`.

- [x] M3 Task 1: `ttcap` board profiles and raw-REPL link (merged)
- [x] M3 Tasks 2-3: throughput script, PIO+DMA capture script (merged)
- [x] M3 Task 4: host capture flow, `ttcap capture` / `ttcap png` (merged 4783a08; four hardware-driven fix rounds)

- [x] Measure USB CDC throughput: RP2040 ~150 KB/s, RP2350 ~650-740 KB/s, bridge = serial (`docs/research/2026-09-15-usb-cdc-throughput.md`)
- [~] `sample_extclk` PIO program for the RP2040 map (12-bit read from GPIO5) and the RP2350 map (GPIOBASE 16) — M3 Task 3, in fix round 1 (shift-left packing ruling)
- [~] MicroPython loader script: PIO + DMA ring + chunked output over the REPL — M3 Task 3, in fix round 1
- [x] First slow-clock capture from hardware: fpga-1 `tt_um_vga_pattern` at 500 kHz, six frames, pixel-exact (`docs/results/2026-09-15-first-capture-fpga1-tt_um_vga_pattern/`)
- [x] Slow-clock capture of tt07 VGA Checkers at 60 kHz (exploration path, one frame, positive syncs)
- [x] `ttcap capture` on the Pi over direct serial (tt07 VGA Checkers, `docs/results/2026-09-15-ttcap-capture-serial-tt07/`)
- [x] tt08 Glyph Mode captured over direct serial (`docs/results/2026-09-15-ttcap-capture-serial-tt08-glyph-mode/`)
- [x] tt08 VGA Tiny Logo reconstructs with glitch tolerance; pinned as a regression fixture
- [x] `libvgaframe`: retroactive first frame (merged)
- [ ] Cross-check the tt07 VGA Checkers frame against an Icarus simulation of the project's source

- [x] M3 Task 5: clock sweep on both board types (`docs/research/2026-09-15-micropython-capture-rate.md`)
- [x] M3 Task 4b: PIO program leak and coalesced overrun lines (merged 88b72eb; board recovered without a power cycle)
- [x] M3 final whole-milestone review: fix wave merged (b23a551); review and ledger archived under `docs/reviews/`. **Milestone 3 complete.**
- [x] M4 Task 2: `counter` + `prbs` with per-frame counter checking (merged 719dbb1)
- [x] M4 Tasks 3-4: `modes` design, iCE40 build flow, bitstreams, CI (merged 1209477; CI green on its first run)
- [x] M4 Task 5: hardware validation of all five designs. **Milestone 4 complete.**

## Milestone 4: calibration designs on the FPGA emulation boards

Plan: `docs/superpowers/plans/2026-09-15-m4-testpatterns.md`.

- [x] M4 Task 1: scaffolding, VESA-correct timing generator, `bars` + `grid`, cocotb, render/check tools (merged 59382ba)

- [x] `tt-vga-testpatterns` repo skeleton with the TT template layout and cocotb
- [x] `tt_um_vgacal_bars`, `_grid`, `_counter`, `_modes`, `_prbs` with reference renderers
- [x] iCE40UP5K builds via `tt_fpga.py harden`, five bitstreams committed (all above 25 MHz)
- [x] Upload to fpga-1 and capture; **pixel-exact comparison passed for bars and grid** (`docs/results/2026-09-15-calibration-loop-fpga1/`)
- [x] Same for `counter`, `modes` and `prbs` on hardware: all pixel-exact; counter verified across five consecutive frames; modes detected 800x600@60 with positive syncs unaided

## Milestone 5: GStreamer plugin and demo

Plan: `docs/superpowers/plans/2026-09-15-m5-gstreamer-and-demo.md`.

- [x] M5 Task 1: `libvgaframe` glitch-tolerant line starts + retroactive first frame (merged 20421f9)
- [x] M5 Task 2: streaming capture API and `ttcap capture --out -` (merged c25be83; 730 k samples/s to stdout on hardware)
- [x] M5 Task 4: `vgacapttsrc` live source and `vgacapbin` (merged 6cb248a; live board to video verified)
- [~] M5 Task 5: `ttcap demo` with PNG, video file, local window and browser view (next)
- [x] M5 Task 3: `vgadecode` GStreamer element (merged e80fe84; pixel-exact on hardware data, MKV carries the project's time base)

- [ ] `vgadecode` element
- [ ] `vgacapttsrc` (serial device and WebSocket URI)
- [ ] `vgacapbin`
- [ ] `ttvga-demo`: PNG + MKV, `autovideosink`, HLS/MJPEG endpoint

## Milestone 6: whole-frame and windowed capture

Plan: `docs/superpowers/plans/2026-09-15-m6-wholeframe-and-compression.md`.

- [ ] `sample_frame` PIO program
- [ ] Whole-frame to SRAM on RP2350; packed / half-frame on RP2040
- [ ] Windowed reassembly validated with `tt_um_vgacal_counter`

## Milestone 7: C firmware and MicroPython module

- [ ] pico-sdk firmware with the command protocol
- [ ] Fork tt-micropython-firmware, USER_C_MODULE
- [ ] Direct serial ownership on the Pi (stop `fpgas-tt`, capture, restart)

## Milestone 8: compression research

- [ ] CPU RLE throughput on RP2040 / RP2350
- [ ] PIO-side run counting feasibility
- [ ] Write-up in `docs/research/`

## Milestone 9: later backends

- [ ] RP1 backend (needs a Pi 5 wired to a TT board)
- [ ] BIO note and interface stub
- [ ] Comparison against a USB VGA capture card when one exists
