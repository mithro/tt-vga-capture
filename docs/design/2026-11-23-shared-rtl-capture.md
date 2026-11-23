# Shared RTL capture library (`vgacap/rtl/`)

Date: 2026-11-23. Status: scope agreed with Tim ("a shared library for VGA
capture in RTL makes sense to include"); module design open.

## Why

Three projects sample a Tiny Tapeout design's `uo_out` and need a vgacap
stream out of it:

- this project, through the RP2 MCU's PIO (`ttcap`);
- `tt-harness-handheld-vga`, inside an Arty A7 / Game Bub FPGA, on the
  design's own clock;
- `tt-harness-fpga-vga`, which today relies on `ttcap` but could sample in
  the iCE40UP5K fabric beside small designs.

Without a shared module each FPGA project writes its own sampler and its own
copy of the chunk framing, and the stream format drifts. `vgacap` already
owns the format, the C/Python reader and `libvgaframe`, so it owns the RTL
writer too, and its tests prove the RTL against the same reader.

## Scope

- `vgacap/rtl/`: plain synthesizable Verilog-2005 (yosys for iCE40,
  Vivado/LiteX for Arty, Verilator/Icarus for simulation). No vendor
  primitives in the core; FIFOs/BRAM behind a small wrapper.
- A sampler that registers `uo_out` on the design clock from the first reset
  clock (reset-aligned, gap-free while the sink keeps up).
- A run-length encoder and chunk framer that emit a byte stream
  (valid/ready) of `VGCH` + `RLE ` chunks; a `TIME` chunk with the
  cumulative `dropped_samples` (msg `overrun`) when the sink stalls and the
  FIFO overflows, so a gap is never silent.
- Tests: cocotb (Icarus), each feeding the RTL a known `uo_out` sequence and
  decoding its output with the existing C and Python readers; the
  calibration designs from `tt-vga-testpatterns` through RTL capture plus
  `libvgaframe` must be pixel-exact against their reference renders.

Not in scope: hashing in RTL (hashes are computed host-side from the
reconstructed frame, one definition for every source).

## Open design points

- **Chunk length is declared up front.** `RLE ` is `u32 pair_count` then
  `(u32 value, u32 run)` pairs, so a streaming encoder must commit to a pair
  count before it has the pairs. Candidate: fixed N pairs per chunk, and at
  stop/flush emit the remainder as single-pair chunks (each of known length).
- **`RLE ` is 8 bytes a pair with an 8-bit value.** On a byte-limited link
  that costs most of the compression a VGA picture offers. A compact chunk
  (u8 value, variable-length run) may be justified; adding a chunk type
  needs reader support in C and Python and a format version note.
- **Link back to the RP2350 on the FPGA boards.** If the UP5K encoder's
  output reaches the MCU (spare `uio` pins), the MCU forwards compressed data
  and the 750 kHz streaming ceiling stops applying to compressible content.
  This overlaps M6 Task 4 / M8 (board-side RLE) and is worth measuring.

## Who

First implementation contributed by the `tt-harness-handheld-vga` session
(its Arty build needs it first), as a PR into `vgacap` reviewed here.

## Keeping the dependency small

Tim, 2026-11-23: "Don't create complicated dependencies between projects, a
little bit of code duplication is better than having a huge complex
dependency tree." So `vgacap/rtl/` is a leaf: a few self-contained `.v`
files with no includes from the rest of `vgacap` and no build-system
coupling. A harness may pin it as a submodule or simply copy the files in
(with the vgacap commit noted); the contract between projects is the stream
format, which the readers check, not the RTL source.
