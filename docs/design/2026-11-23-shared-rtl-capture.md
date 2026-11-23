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

- `vgacap/rtl/`: **Migen/LiteX source with its generated Verilog
  committed alongside** (Tim, 2026-11-23, chosen over hand-written Verilog:
  "migen/litex with generate verilog included. most projects here are
  litex"). LiteX users import the Migen module; yosys-only flows (iCE40)
  and Verilator/Icarus use the `.v`. The generated file carries a header
  naming its source, is never hand-edited, and a test regenerates it and
  fails if the committed copy is stale. No vendor primitives in the core;
  FIFOs/BRAM behind a small wrapper.
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

## Who, and in what order (updated 2026-11-23)

1. **Sampler** (`tt-harness-handheld-vga`): `uo_out` registered on the
   design clock from the first reset clock, a sample-valid / overflow
   interface and a clock count, no vendor primitives. Developed and used in
   that repo first, then contributed to `vgacap/rtl/` (Migen source,
   generated Verilog, staleness test, a test against the vgacap readers);
   that repo keeps its own copy recording the vgacap commit it matches
   rather than pulling from vgacap. On Arty the project clock is *stepped*
   from the 50 MHz domain, one pulse whenever the recorder has room, and one
   `uo_out` byte per project clock goes over the UART; the host writes the
   `RAW ` chunk. Project, sampler and recorder share one synchronous domain,
   so nothing can be dropped. Byte 0 is the value after the first reset
   clock's rising edge. Raw rather than `RLE ` because a busy design (Anton's
   dottee changes ~64% of pixels per frame) would make 8-byte pairs several
   times larger than the samples. (Corrected 2026-11-23: an earlier draft
   said DDR3.)
2. **RLE encoder and chunk framer**: for the byte-limited paths (iCE40 to
   RP2350, UART). Its real users are this project and `tt-harness-fpga-vga`,
   so it is specified here; not started.

Leaning on the open points, from that session's review:

- Buffer a chunk's pairs in one block RAM (e.g. 256 pairs = 2 KiB, fits a
  UP5K EBR budget) and emit the header when the chunk is full or flushed, so
  `pair_count` is always exact and the flush path is the ordinary path.
- If a compact chunk is added: `u8 value` + LEB128 run (worst case 2 bytes
  a sample), and the encoder falls back to `RAW ` for any chunk where RLE
  would be larger, so no content can expand the stream. Needs Tim's
  agreement and C + Python reader support.

## Keeping the dependency small

Tim, 2026-11-23: "Don't create complicated dependencies between projects, a
little bit of code duplication is better than having a huge complex
dependency tree." So `vgacap/rtl/` is a leaf: a few self-contained Migen modules and
their generated `.v` files with no includes from the rest of `vgacap` and no build-system
coupling. A harness may pin it as a submodule or simply copy the files in
(with the vgacap commit noted); the contract between projects is the stream
format, which the readers check, not the RTL source.
