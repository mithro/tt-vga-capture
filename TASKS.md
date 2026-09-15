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
- [~] `vgacap/frame`: sync polarity + timing detection, mode table, active-area location, RGB24 framebuffer, frame callback (implemented, under review)
- [ ] Synthetic stream generator (C and Python) for every mode table entry and polarity
- [~] Partial-frame accumulation for `FRAM` (implemented, under review)
- [ ] Unit tests and CI

## Milestone 3: first real picture from Welland (MicroPython PIO prototype)

- [ ] Measure USB CDC throughput of the RP2040 boards through the bridge and (once SSH works) on the Pi directly
- [ ] `sample_extclk` PIO program for the RP2040 map (12-bit read from GPIO5) and the RP2350 map (GPIOBASE 16)
- [ ] MicroPython loader script: PIO + DMA ring + chunked output over the REPL
- [ ] Slow-clock capture of tt07 VGA Checkers / tt08 VGA Tiny Logo / tt08 Glyph Mode; first PNG committed to `docs/results/`

## Milestone 4: calibration designs on the FPGA emulation boards

- [ ] `tt-vga-testpatterns` repo skeleton with the TT template layout and cocotb
- [ ] `tt_um_vgacal_bars`, `_grid`, `_counter`, `_modes`, `_prbs` with reference renderers
- [ ] iCE40UP5K builds via `tt_fpga.py harden`, bitstreams committed
- [ ] Upload to fpga-1 and capture; pixel-exact comparison

## Milestone 5: GStreamer plugin and demo

- [ ] `vgadecode` element
- [ ] `vgacapttsrc` (serial device and WebSocket URI)
- [ ] `vgacapbin`
- [ ] `ttvga-demo`: PNG + MKV, `autovideosink`, HLS/MJPEG endpoint

## Milestone 6: whole-frame and windowed capture

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
