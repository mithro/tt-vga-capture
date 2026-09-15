# The `vgacap` capture stream format (version 1)

Date: 2026-09-15. Implemented in `mithro/vgacap` (`include/vgacap/stream.h`,
`src/stream/`, `python/vgacap/stream.py`). This note is the normative
description; the code and its tests are the proof.

## Why this shape

- **One decoder, several encodings.** The reader turns every chunk type
  into `(value, run)` pairs, so the reconstruction library has a single
  push function and run-length input is free to consume. VGA blanking is
  long runs of a constant sync value, so run-based decoding also makes
  RLE capture cheap on the host.
- **DMA words verbatim.** `RAW` and `FRAM` chunks store the 32-bit words the
  PIO's autopush/DMA produced, with the header saying how many samples a
  word holds and whether the first sample sits in the low or the high
  bits. The microcontroller never repacks; a 12-bit RP2040 read (uo_out is
  not contiguous there) and an 8-bit RP2350 read are both just "write the
  buffer".
- **A signal map, not an assumption.** The header says which sample bit
  carries hsync, vsync and each colour bit, so the same decoder handles
  the RP2040's `[uo3..uo0][ui3..ui0][uo7..uo4]` layout, the plain Tiny VGA
  byte, a logic analyser's channel order, or a simulator dump.
- **Self-describing chunks** so tools can skip what they do not know and
  diagnostics (`TIME`) can be interleaved with data.

## Container

Chunk = `tag[4]` ASCII, `u32` little-endian payload length, payload. All
multi-byte integers little-endian. The first chunk is `VGCH`; unknown tags
are skipped.

## `VGCH` header

| offset | type | field |
|---|---|---|
| 0 | u16 | version = 1 |
| 2 | u8 | sample_bits: 8, 12, 16 or 32 |
| 3 | u8 | mode: 0 extclk, 1 selfclk, 2 event, 3 unknown |
| 4 | u32 | clock_hz (0 = unknown) |
| 8 | u8[8] | signal_map: sample bit index of hsync, vsync, r1, r0, g1, g0, b1, b0; 0xFF = absent |
| 16 | u8 | samples_per_word: 1, 2, 4 or 8 |
| 17 | u8 | flags: bit0 = first sample of a word is in the most significant slot |
| 18 | u16 | desc_len |
| 20 | u8[desc_len] | desc, UTF-8 |

Tiny VGA Pmod map: `(7, 3, 0, 4, 1, 5, 2, 6)`. RP2040 demo-board 12-bit
read from GPIO5: `(11, 3, 0, 8, 1, 9, 2, 10)`.

## Data chunks

| tag | payload |
|---|---|
| `RAW ` | `u32 sample_count`, then `ceil(sample_count / samples_per_word)` words. Sample i is in word `i / spw`, slot `i % spw` (or `spw-1-i%spw` with flags bit0), shifted by `slot * sample_bits`. |
| `RLE ` | `u32 pair_count`, then `(u32 value, u32 run)` pairs. |
| `FRAM` | `u32 frame_counter, u16 first_line, u16 line_count, u32 clocks_per_line, u32 sample_count`, then words as `RAW `. Samples start at the leading edge of the hsync pulse of `first_line`. |
| `EVNT` | `u32 event_count`, then `(u64 clock, u32 value)`; clocks strictly increasing; each value holds until the next event, the last for one clock. |
| `TIME` | `u64 host_time_ns, u32 clock_hz, u32 dropped_samples, u16 msg_len, msg`. |

## Tools

- `vgacap-dump <file>`: chunk list, total samples, FNV-1a over the expanded
  samples (cross-checked against the Python reader in CI).
- `vgacap-frames <file> <prefix>`: reconstructed frames as binary PPM.
- `uv run vgacap-bin2stream <dump.bin> <out.vgacap>`: wrap a one-byte-per-clock
  simulator dump.

## Reconstruction notes learned while testing

- A frame is emitted at the next frame boundary once the timing is known
  (`locked` after two agreeing frames, or an exact table match of clocks
  per line and lines per frame, or a forced mode). A capture that starts
  mid-frame therefore needs one boundary plus one full frame before the
  first picture: capture at least three frame periods.
- `FRAM` windows resolve their mode by the chunk's clocks-per-line when
  nothing else is known; clocks-per-line is unique across the built-in
  mode table (800, 832, 840, 900, 1024, 1056, 1344).
