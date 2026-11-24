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

## Milestone 5: GStreamer plugin and demo — **complete**

- [x] M5 Task 6: CI for the GStreamer plugin and `tools/hil.py`/`hil.sh` (merged 4b005b2, CI green; review fixes applied; all nine checks PASS on fpga-4, bars pixel-exact: `docs/results/2026-11-23-hil-fpga4/`). **Milestone 5 complete.**

Plan: `docs/superpowers/plans/2026-09-15-m5-gstreamer-and-demo.md`.

- [x] M5 Task 1: `libvgaframe` glitch-tolerant line starts + retroactive first frame (merged 20421f9)
- [x] M5 Task 2: streaming capture API and `ttcap capture --out -` (merged c25be83; 730 k samples/s to stdout on hardware)
- [x] M5 Task 4: `vgacapttsrc` live source and `vgacapbin` (merged 6cb248a; live board to video verified)
- [x] M5 Task 5: `ttcap demo` (merged 375e368; four fix rounds, proven on fpga-1)
- [x] M5 Task 3: `vgadecode` GStreamer element (merged e80fe84; pixel-exact on hardware data, MKV carries the project's time base)

- [ ] `vgadecode` element
- [ ] `vgacapttsrc` (serial device and WebSocket URI)
- [ ] `vgacapbin`
- [x] `ttcap demo`: PNG, MKV, `--window`, MJPEG browser view (proven on fpga-1)

## Shared code with the harness projects (agreed 2026-11-23)

Design note: `docs/design/2026-11-23-shared-rtl-capture.md`.

- [-] ~~Per-frame hash PR from `tt-harness-fpga-vga`~~: withdrawn 2026-11-23 under Tim's no-dependency-tree rule; that project keeps its own cutter and hash (`docs/frame-definition.md` there) and runs `ttcap` as a program
- [ ] `vgacap/rtl/`: shared Verilog sampler + RLE chunk writer, cocotb-tested against the C/Python readers (sampler first, PR from `tt-harness-handheld-vga` after Tim approves its design; RLE encoder specified here)
  - [x] `vgacap_raw_framer` (RAW + overrun TIME chunks, Migen + generated Verilog; vgacap PR #4): Migen and Icarus simulation, cocotb in tt-vga-testpatterns `tt_um_vgacal_framer` (branch `framer-design`), and on fpga-4 at 250 kHz (whole frame exact) and 25 MHz (gap-free RAM windows); `docs/results/2026-11-24-rtl-framer-fpga4/`
- [ ] Decide `RLE ` chunk-length handling and whether a compact RLE chunk is justified

## Milestone 6: whole-frame and windowed capture

Plan: `docs/superpowers/plans/2026-09-15-m6-wholeframe-and-compression.md`.

- [x] Task 1: shared board prelude `ttcap/mp/prelude.py` (vgacap PR #1, CI green, HIL 9/9 on fpga-1; awaiting Tim's merge)
- [x] Tasks 2+3: `frame_rp2.py` whole-frame + windowed capture at the real clock (vgacap PR #2): PIO vsync/hsync trigger, phase-locked `in [P-1]` sampler, control-block DMA, stopper; all five calibration designs pixel-exact on fpga-4 at 25/28.25/40 MHz; `docs/results/2026-11-24-frame-capture-fpga4/`
- [x] Windowed reassembly validated with `tt_um_vgacal_counter` (torn, and reported as such) and `grid` (exact)
- [x] `ttcap.emu`: emulated RP2040/RP2350 running the exact built script (vgacap PR #2)
- [ ] Frame/window mode on a real RP2040 board: emulated only -- no RP2040 Tiny Tapeout board is reachable (tt04's listed Pi, sw2 p48, is the label-station port; PS1 has only Artys). Needs one connected.
- [x] `vgacap-frames` reports measured sync polarities in frame mode (was the mode table's)
- [x] Task 4 measurement: viper RLE 3.06 M samples/s on RP2350; the 8-byte `RLE ` pair caps the gain at +12%, a compact pair would give ~2x (`docs/research/2026-11-24-board-rle-throughput.md`)
- [ ] DECISION FOR TIM: add a compact RLE chunk (u8 value + LEB128 run) to the vgacap format? Then build it (board viper encoder, C/Python readers, RTL encoder)
- [x] Task 5: measurement write-up per mode and board (`docs/research/2026-11-24-capture-modes-measured.md`; RP2040 frame/window still emulation-only)
- [x] Frame/window modes in `vgacapttsrc`, `vgacapbin` and `ttcap demo` (live on tt09 silicon)
- [x] Real silicon at its design clock: tt09 VGA logo, Nyan Cat (25.175 MHz), VGA clock (31.5 MHz)

## Milestone 7: C firmware and MicroPython module

- [x] pico-sdk firmware with the command protocol (vgacap PR #7, `ttcap capture --firmware picosdk`): simulated-board tests, and on fpga-4 from RAM (no_flash UF2 via BOOTSEL) frame/window/stream pixel-exact, board files unchanged; live GStreamer `ttcap demo --firmware picosdk` 24/24 frames exact (PR #8); ASIC boards via `--asic-index` (PR #9), tt09 logo clean (`docs/results/2026-11-24-picosdk-firmware-fpga4/`)
- [~] Fork tt-micropython-firmware, USER_C_MODULE: vgacap PR #10 (`ttcap capture --firmware mpy-module`), fork branch `vgacap-module` (UF2 release `dev-vgacap-module`); 18 module tests on the unix port + simulated board, CI green. Hardware test needs the image *flashed* onto a board (not RAM-only): waiting on Tim's go-ahead
- [x] Direct serial ownership on the Pi (stop `fpgas-tt`, capture, restart): fpga-4 stream + 25 MHz frame pixel-exact, tt09 silicon frame mode; no throughput gain over the bridge on either Pi (`docs/results/2026-11-24-direct-serial-fpga4/`)

## Milestone 8: compression research

- [~] CPU RLE throughput: RP2350 measured (`docs/research/2026-11-24-board-rle-throughput.md`); RP2040 needs a board
- [x] PIO-side run counting: `ttcap capture --mode rle` (vgacap PR #6), exact on the emulator and on fpga-4 up to 25 MHz (locked, 150 MHz sysclk) on bars and prbs; RP2040 emulated only
- [x] Write-up in `docs/research/` (`2026-11-24-board-rle-throughput.md`, `2026-11-24-pio-run-counting.md`)

## Milestone 9: later backends

- [x] RP1 backend `vgacap-rp1` (vgacap PR #3): proven by loopback on pi-sw2-p4 at 500 k samples/s (counter exact, bars pixel-identical); emulation test of its program words
  - [ ] Against a real TT board once a Pi 5 is wired to one (checked daily)
  - [ ] Above 0.5 M samples/s: cyclic-DMA kernel module (rpi5-rp1-pio-bench) instead of stock rp1-pio
- [~] BIO backend built against the BIO simulator (Tim, 2026-11-24: fine to build against it): capture programs bit-exact to 40 MHz in bio-sim; no BIO hardware on fpgas.online
  - [x] Research note + capture programs passing in `bio-sim` (`docs/research/2026-11-24-bio-capture-feasibility.md`)
  - [ ] FIFO drain path (BDMA core or host `RXFn`) in the full-SoC Verilator flow
  - [ ] Firmware + host transport (vgacap chunks over USB HS)
- [ ] Comparison against a USB VGA capture card (Tim: will appear on tinytapeout.fpgas.online, with a camera on a VGA screen; checked daily)

## Milestone 10: simulation traces (with tinytapeout-vga-videos)

Agreed 2026-11-24. That project's spec is
`tinytapeout-vga-videos/docs/superpowers/specs/2026-11-24-raw-frames-and-hash-methods-design.md`.
It writes these on vgacap branches; this project reviews them before merge.

- [x] Design note: 64-bit samples plus an RLE64 chunk (format v2), put to Tim together with the compact-RLE decision (`docs/design/2026-11-25-format-v2-runs.md`, m10-format-note 84de19c; decided 2026-11-25: RUNS, boards after M10, skip-by-length)
- [x] Benchmark libvgaframe on run-encoded input at 1.5e9 clocks (`docs/research/2026-11-25-libvgaframe-runs-benchmark.md` on m10-bench-note; busy 45.7 ns/clock, 4.2x over budget: plan Task 7a)
- [x] Samplers `tb-v1` / `centre-v1` (clocks per pixel other than 1, including below 1); longer lines and modes not in the table (vgacap m10-samplers dbe5a68, local)
- [ ] rgb6 output beside rgb24
- [x] Vendored zstd, zlib (libfst needs it), SHA-256 and fstapi as an optional CMake target (vgacap m10-third-party 6c0e45f)
- [ ] `vgacap-export --format fst|vcd`, including decoded signals and a .gtkw file
- [ ] Implementation plan: `docs/superpowers/plans/2026-11-24-m10-simulation-traces.md` (reviewed here before work starts)
- [ ] Trace container: zstd seekable blocks with `BLKH` block headers, seek-table rebuild for cut-off traces
- [ ] `META` chunks (opening run parameters, closing status) in the C writer/reader and the Python mirror
- [ ] Trace writer with an inline push and a double-buffered compressor thread (host-only target)
- [x] Shared 12-mode table (tb.cpp's five added, marked so `vgaframe_mode_match_cpl` skips them); ttcap `--vga-mode` rejects the marked modes (vgacap m10-modes 8f47687, local)
- [ ] libvgaframe raw-frame callback at every frame boundary, buffers cleared at every boundary
- [x] Shared calibration and frame clock (port of tb.cpp:191-230, 361-378) (vgacap m10-samplers 4133c8f, local)
- [x] `vgacap-sample`: both samplers and the hash methods in one pass; stores, `frames.txt`, hash files, PNG pipe (vgacap m10-sample-tool 12dfaf7, local; speed in Task 16a)
- [ ] `tb-v1` test vectors from tinytapeout-vga-videos' `tb.cpp` comparison
