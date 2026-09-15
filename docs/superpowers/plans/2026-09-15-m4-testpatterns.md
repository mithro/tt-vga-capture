# Milestone 4: calibration designs for the FPGA emulation boards — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verilog calibration designs in Tiny Tapeout template form, each with a cocotb test and a Python reference renderer that produces the exact expected picture, built for the iCE40UP5K FabricFox breakout and uploaded to the Welland FPGA emulation boards so the capture pipeline can be checked pixel-exactly.

**Architecture:** One directory per design under `designs/<name>/` in `mithro/tt-vga-testpatterns` with `info.yaml`, `src/*.v`, `docs/info.md`, `test/` (cocotb + Makefile). A shared `hvsync_generator.v` (same interface as the Tiny Tapeout VGA playground) provides timing. `tools/render.py` holds the reference renderers (numpy) and `tools/dump_uo_out.py` (exists) dumps simulated `uo_out` per clock; `tools/check.py` wraps a dump into a `vgacap` stream, runs `vgacap-frames`, and diffs against the reference render. `tools/build.py` runs the tt-support-tools `tt_fpga.py harden` flow (yosys, nextpnr-ice40 `--up5k --package sg48`, FabricFox v2 pcf, icepack) with oss-cad-suite, writing `bitstreams/<name>.bin`. `tools/upload.py` posts a bitstream to a Welland board's daemon and enables it (controller runs this).

**Tech Stack:** Verilog-2005, Icarus Verilog + cocotb 2 (`uv`), numpy/Pillow, oss-cad-suite (`~/tools/oss-cad-suite/bin`), tt-support-tools (`tt_fpga.py`, `fpga/tt_fpga_top.v`, `fpga/tt_fpga_fabricfoxv2.pcf`), the `vgacap` tools.

**Spec:** `docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md` §5.8 and §8.

## Global Constraints

- Apache-2.0; SPDX headers on every file (`// SPDX-License-Identifier: Apache-2.0` in Verilog).
- Tiny VGA Pmod mapping on `uo_out`: `{hsync, b0, g0, r0, vsync, b1, g1, r1}` = bits 7..0.
- Timing: 640x480@60 = 800 clocks/line (640 active, 16 front, 96 sync, 48 back), 525 lines (480 active, 10 front, 2 sync, 33 back), both syncs active low; 800x600@60 = 1056/628 (800,40,128,88 / 600,1,4,23), syncs active high; 720x400@70 = 900/449 (720,18,108,54 / 400,12,2,35), hsync low, vsync high.
- Every design must simulate with `tools/dump_uo_out.py` and reconstruct pixel-exactly through `vgacap-frames` against its reference render; that check is the acceptance test.
- Designs must fit an iCE40UP5K (5280 LUTs): no large ROMs, no multipliers in critical paths; target `nextpnr --freq 25`.
- Python via `uv` only; the repo gets a `pyproject.toml` with numpy, pillow, cocotb>=2, pytest.
- The project clock is `clk`; all outputs registered on `posedge clk`; synchronous active-low `rst_n`.

## File structure

```
tt-vga-testpatterns/
  pyproject.toml  Makefile (top-level: sim/check/build for all designs)
  common/hvsync_generator.v      parameterised VGA timing (mode selected by parameters)
  designs/tt_um_vgacal_bars/{info.yaml,src/project.v,docs/info.md,test/{Makefile,test_bars.py}}
  designs/tt_um_vgacal_grid/...
  designs/tt_um_vgacal_counter/...
  designs/tt_um_vgacal_modes/...
  designs/tt_um_vgacal_prbs/...
  tools/render.py   reference renderers: bars(), grid(), counter(frame), modes(mode, ui_in), prbs(frame)
  tools/check.py    simulate -> stream -> vgacap-frames -> diff vs render (exit 1 on any pixel mismatch)
  tools/build.py    harden all designs with tt_fpga.py, write bitstreams/
  tools/upload.py   POST bitstream to a Welland daemon and enable it
  bitstreams/*.bin  committed outputs
```

## Designs (pictures are 640x480 unless stated)

| Design | Picture | Reference |
|---|---|---|
| `tt_um_vgacal_bars` | 64 vertical bars of 10 px each, colour index = x / 10 (rr gg bb as bits 5..0), 480 rows identical | `render.bars()` = `(x // 10) & 0x3F` |
| `tt_um_vgacal_grid` | white (0x3F) where `x % 8 == 0` or `y % 8 == 0`, else dark red 0x10; plus a 1-px white border at x=0, x=639, y=0, y=479 | `render.grid()` |
| `tt_um_vgacal_counter` | 8-bit frame counter (increments at each vsync) drawn as 8 horizontal blocks 80x60 px at the top (bit set = white, clear = blue 0x03), the 9-bit line number drawn as a 9-bit binary strip of 60x20 px blocks in every 40-line band's first row region, rest black | `render.counter(frame)` |
| `tt_um_vgacal_modes` | `ui_in[1:0]` selects 0 = 640x480@60, 1 = 800x600@60, 2 = 720x400@70; `ui_in[2]` inverts hsync polarity, `ui_in[3]` inverts vsync polarity; picture = bars pattern scaled to the active width (bar width = active/64) | `render.modes(mode, ui_in)` |
| `tt_um_vgacal_prbs` | per-pixel 6-bit value from a 16-bit LFSR (x^16+x^14+x^13+x^11+1) seeded with `0xACE1 ^ frame` at the start of each frame's active area, advanced once per active pixel | `render.prbs(frame)` |

## Tasks

### Task 1: repo scaffolding, timing generator, `bars` and `grid` with cocotb and the check tool
- `pyproject.toml` (numpy, pillow, cocotb>=2.0, pytest; script `ttp-check = "tools.check:main"` is optional), `common/hvsync_generator.v` with parameters `H_ACTIVE, H_FRONT, H_SYNC, H_BACK, V_ACTIVE, V_FRONT, V_SYNC, V_BACK, H_POL, V_POL` and outputs `hsync, vsync, hpos, vpos, display_on` (registered, one clock of latency documented: `hpos/vpos` refer to the pixel whose colour is output next cycle; the design registers colour so sync and colour line up).
- `designs/tt_um_vgacal_bars` and `designs/tt_um_vgacal_grid` with `info.yaml` (yaml_version 6, pinout naming R1/G1/B1/VSync/R0/G0/B0/HSync), `docs/info.md`, cocotb test that runs 2 frames and checks hsync period 800, vsync period 525 lines, and samples a few pixels against `tools/render.py`.
- `tools/render.py` and `tools/check.py`; `make check` runs the dump → stream → frames → diff for every design present. Check depends on `vgacap` being built at `../vgacap/build` (path configurable via `VGACAP_BUILD`).
- Commit as you go; `make check` must pass for both designs.

### Task 2: `counter` and `prbs`
- As above, with reference renderers taking the frame index; the check tool compares frames 1..N individually (frame counter observed in the picture must equal the reconstructed frame index offset).

### Task 3: `modes`
- Parameterised timing selected at runtime: three `hvsync_generator` instances or one generator with muxed constants (keep it small); check all three modes and both polarity inversions through the tool (`vgacap-frames` must report the right mode and polarities).

### Task 4: iCE40 builds
- `tools/build.py`: clones/pins tt-support-tools (commit recorded), runs `tt_fpga.py harden --breakout-target fabricfox` per design with `PATH` including oss-cad-suite; commits `bitstreams/*.bin` and a `bitstreams/README.md` with sizes, nextpnr max-frequency and the commit hashes.

### Task 5 (controller): upload to fpga-1 and capture
- `tools/upload.py` + hardware runs; results to `tt-vga-capture/docs/results/`.
