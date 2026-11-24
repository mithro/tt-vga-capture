# VGCH format v2: wide samples, a `RUNS` chunk and a trace container

Date: 2026-11-25.

Status: proposed, awaiting Tim's decision (decision 1 of the
tinytapeout-vga-videos spec).

Decision: (pending)

Sources, cited by short name below:

- **spec**: `tinytapeout-vga-videos/docs/superpowers/specs/2026-11-24-raw-frames-and-hash-methods-design.md`
  (sections "Layer 1: the trace", "Performance budget", "Shared code: vgacap").
- **stream.h**: vgacap `include/vgacap/stream.h` on branch `fw-picosdk`
  (has `vgacap_writer_attach`); **reader.c**, **writer.c** are its `src/stream/`.
- **rle-note**: `docs/research/2026-11-24-board-rle-throughput.md`.
- **rtl-note**: `docs/design/2026-11-23-shared-rtl-capture.md`.

## What is being decided

Two needs have the same shape and this note proposes one format change for
both.

1. **Simulation traces.** The pipeline records every pin of a Tiny Tapeout
   design: 43 bits per sample, two samples per clock (spec, "What is
   recorded"). vgacap today holds samples of 8, 12, 16 or 32 bits
   (stream.h `vgacap_header_t.sample_bits`) in `RAW `/`RLE `, and `RLE ` is a
   32-bit value plus a 32-bit run. The longest simulation is 1.2e10 samples
   (spec, "Size and format"), so a run can exceed 2^32 and run lengths must be
   unbounded. The `clk` bit toggles every sample, so it must not take part in
   run comparison (spec, "The clock in a run-encoded trace").
2. **The board's compact RLE** (the question left open by the rle-note and
   the rtl-note). The rle-note measures, per 16,384-sample buffer on the
   RP2350: `RAW ` 23.4 ms (700 k samples/s), `RLE ` as specified 20.9 ms
   (784 k, +12%), a compact pair of about 3 bytes (u8 value + LEB128 run)
   11.2 ms (1.46 M, 2.1x). It recommends the compact chunk and notes the RTL
   encoder should emit the same chunk.

**Answer to the compact-RLE question: yes, and it is the same chunk.** The
board's pair is a `RUNS` chunk with `sample_bits = 8`: `vbytes = 1`, so a
pair is one value byte plus a LEB128 run, exactly the rle-note's "u8 value +
LEB128 run". The simulation's 43-bit pair is the same chunk with
`sample_bits = 43`, `vbytes = 6`. One chunk type, one reader path, one Python
mirror, and the RTL encoder (rtl-note) emits the same thing as the board.
`RLE ` stays readable (existing captures, and the `pio-rle` firmware that
emits it, spec "Shared code"); new writers use `RUNS`.

## Proposed layouts

All integers are little-endian. A chunk is `tag[4]`, `u32` payload length,
payload, as today (stream.h header comment).

### VGCH version 2

Bytes 0-19 are version 1's layout (the wire layout in writer.c
`vgacap_writer_init`: `u16 version`, `u8 sample_bits`, `u8 mode`,
`u32 clock_hz`, `u8[8] signal_map`, `u8 samples_per_word`, `u8 flags`,
`u16 desc_len`), with two changes:

- `version` is 2.
- `sample_bits` may be 1..64. `samples_per_word` is 0 when
  `sample_bits > 32`, and `RAW `, `FRAM`, `RLE ` and `EVNT` are then not
  allowed (their values are 32 bits). For `sample_bits <= 32` the version 1
  rules for `samples_per_word` are unchanged.

Then four new bytes:

| offset | type | field |
|---|---|---|
| 20 | u8 | `samples_per_clock`: 1 or 2 (1 for board captures) |
| 21 | u8 | `clock_bit`: 0..63, or 0xFF for none |
| 22 | u8 | `clock_first`: 0 or 1, the clock bit's value in sample 0 |
| 23 | u8 | reserved, must be 0 |

Then `desc_len` bytes of description. The chunk length is `24 + desc_len`, so
at most 279 (`desc_len` is at most 255, stream.h `VGACAP_DESC_MAX`).

Validity rules:

- a `clock_bit` other than 0xFF requires `samples_per_clock == 2`;
- `clock_first` must be 0 when there is no clock bit;
- in every value, bits at or above `sample_bits` must be 0, so each value
  has one encoding.

A version 1 header reads as `samples_per_clock = 1`, `clock_bit = 0xFF`,
`clock_first = 0`. A stream with a `clock_bit` may contain only `RUNS`,
`BLKH`, `META` and `TIME` chunks.

Compatibility: the current reader rejects any version other than 1
(reader.c:118, "unsupported version"), so a version 1 reader fails cleanly on
a v2 stream instead of misreading it. A v2 reader reads v1 streams unchanged.

### `RUNS`

Payload: `u32 pair_count`, then `pair_count` pairs. Each pair is:

- `value`: `vbytes = ceil(sample_bits / 8)` bytes, little-endian, with the
  clock bit stored as 0;
- `run`: LEB128 u64, at least 1, minimal encoding (no trailing `0x80 0x00`),
  at most 10 bytes, with the 10th byte at most `0x01`.

The chunk length must equal `4 +` the pairs' bytes exactly. A pair is
`vbytes + 1..10` bytes: 7 to 16 bytes at 43 bits, 2 to 11 at 8 bits.

Clock regeneration: the reader sets the clock bit of each run's value to
`clock_first ^ (n & 1)`, where `n` is the run's first sample. The run event
therefore carries the full value of the run's first sample, and the clock
bit of every later sample in the run is that value's clock bit toggled each
sample (spec, "Shared code", row 1; "The clock in a run-encoded trace"). With
no clock bit, the value is used as stored.

Consequence for the API (spec, "Shared code", row "64-bit values and long
runs through the API"): the reader's run event becomes a 64-bit value and a
64-bit run. This is an ABI change to `vgacap_event_t.u.run` in stream.h,
which today is `uint32_t value, run`.

### `BLKH`

Payload: `u64 first_sample`, the sample number of the block's first sample
(the block's `n` for clock regeneration).

### `META`

Payload: 1..4096 bytes of UTF-8 text, `key=value` lines, each ending `\n`.
The first line is `meta=open` or `meta=close`.

- Keys in the opening chunk: `project`, `override`, `calib_seconds`,
  `seconds`, `simulator`, `harness`, `layout=tt-um-43`. The clock is the
  header's `clock_hz` alone.
- Keys in the closing chunk: `capture_after_clock`, `status`, `frames`.

`layout=tt-um-43` names the 43-bit sample layout (spec, "What is recorded":
`uo_out` bits 0-7, `uio_out` 8-15, `uio_oe` 16-23, `ui_in` 24-31, `uio_in`
32-39, `rst_n` 40, `ena` 41, `clk` 42). Because `uo_out` is the low byte,
the header's `signal_map` can carry the ordinary Tiny VGA map
`{7,3,0,4,1,5,2,6}` unchanged (spec, "What is recorded").

### Container

A trace file is zstd's seekable format (spec, "Size and format"). Each zstd
frame is one block. The seek table is a skippable frame at the end, so plain
`zstd -d` yields the whole VGCH stream.

- Block 0 is `VGCH`, `META(open)`, `BLKH(0)`, then `RUNS`. Every later block
  is `BLKH(first)`, then `RUNS`.
- The last block ends with `META(close)`.
- A block closes before its uncompressed size would pass 16 MiB minus
  64 KiB, or at 2^24 clocks (`2^24 * samples_per_clock` samples). A run that
  would cross the boundary is split.

The 16 MiB bound is `VGACAP_MAX_CHUNK_LEN` (stream.h); the 64 KiB margin
leaves room for the chunk headers, `BLKH` and `META(close)`. At 7 bytes a
run, 16 MiB minus 64 KiB (16,711,680 bytes) holds at most about 2.39
million runs (my arithmetic: 16,711,680 / 7).

## Worked example

A 43-bit stream: the header, then one `RUNS` chunk of two pairs.

Header fields: version 2, `sample_bits` 43, mode 2 (event), `clock_hz`
25,175,000 (0x018023D8), Tiny VGA signal map, `samples_per_word` 0, flags 0,
`desc_len` 0, `samples_per_clock` 2, `clock_bit` 42 (0x2A), `clock_first` 0.

```
56 47 43 48  18 00 00 00                       "VGCH", length 24
02 00 2b 02  d8 23 80 01                       version 2, bits 43, mode 2, clock_hz 25175000
07 03 00 04 01 05 02 06                        signal_map
00 00 00 00                                    samples_per_word 0, flags 0, desc_len 0
02 2a 00 00                                    samples_per_clock 2, clock_bit 42, clock_first 0, reserved
```

`RUNS`: `rst_n` and `ena` high (bits 40 and 41, 0x0300_0000_0000), a run of
301 samples (LEB128 `ad 02`: 0x2D | 0x80, then 2; 2 * 128 + 45 = 301), then
the same with `uo_out` bit 7 (hsync) also set (0x0300_0000_0080), run 1.
`vbytes = 6`, so each value is six little-endian bytes. The chunk length is
`4 + (6 + 2) + (6 + 1) = 19 = 0x13`.

```
52 55 4e 53  13 00 00 00                       "RUNS", length 19
02 00 00 00                                    pair_count 2
00 00 00 00 00 03  ad 02                       value 0x030000000000, run 301
80 00 00 00 00 03  01                          value 0x030000000080, run 1
```

Decoded: pair 1 covers samples 0..300; `n = 0`, so its clock bit is
`0 ^ 0 = 0`: first-sample value 0x030000000000. Pair 2 starts at sample 301;
`n & 1 = 1`, so its clock bit is 1: first-sample value 0x070000000080 (the
added 0x0400_0000_0000 is the clock bit). Total 59 bytes. The bytes were
produced and decoded back, checking every validity rule above, by a
throwaway Python script (not committed); output recorded in the task report.

## Costs and the sizes behind the choice

Figures are from the spec or the rle-note unless marked as my arithmetic.

- **Pair size**, simulation (43 bits): 6 value bytes plus a 1-10 byte run.
  The spec's own estimate is 7-7.5 bytes a run ("How it is written"): runs
  up to 127 samples take a 1-byte run (7 bytes), up to 16,383 take 2 (8
  bytes).
- **Busiest designs**: up to about one run per clock, two with logic on both
  edges, so 35-70 MB/s of encoded data at the fastest simulation (spec,
  "How it is written"; 4.61 M clocks/s fastest, "Performance budget"). My
  check: 2 x 4.61 M runs/s x 7 B = 64.5 MB/s, x 7.5 B = 69.2 MB/s.
- **Board**, 8 bits: the rle-note's 1,359 pairs per 16,384-sample buffer is
  10,872 bytes as `RLE ` (8 B a pair, matches the note) and about 3 B a
  pair compact, about 4.1 KB (my arithmetic: 1,359 x 3 = 4,077). Minimum is
  2 B a pair (1,359 x 2 = 2,718). Busy content (runs of about 1) expands
  under any RLE, so the board's per-buffer fallback to `RAW ` (rle-note)
  remains; `RUNS` does not change it.
- **Run splitting at buffer ends**: a writer may end a `RUNS` chunk in the
  middle of a long run and begin the next with the same value. Readers must
  not assume runs are maximal across chunks. (The writer's `pair_count` is
  declared up front, as `RLE ` is today; see the rtl-note's open point on
  fixed-N chunks with single-pair remainders. The format allows that.)

## Alternatives

### A. Planar: `uo_out` per sample, plus a 64-bit-valued `EVNT`

Needed only if rollout step 2 shows the busiest designs over budget (spec,
"Performance budget": the trace-recording target is 5% of simulation wall
time, and post-simulation plus compression is 5% of CPU; the spec estimates
compression alone at 4-14% of a core for the busiest designs, using zstd's
0.5-1 GB/s per core).

- What it stores: `uo_out` as one plain byte per sample (2 bytes a clock,
  both halves kept, no run overhead) and the other 34 pins as change events
  (spec, "Performance budget").
- Cost against `RUNS`: at the fastest simulation `uo_out` is 2 x 4.61 M =
  9.2 MB/s regardless of content (my arithmetic), against 35-70 MB/s for
  `RUNS` on the busiest designs. A quiet design loses: `RUNS` stores
  nothing during long constant stretches, planar still stores two bytes a
  clock.
- Format work it adds, beyond `RUNS`: an `EVNT` with a 64-bit value (today
  64-bit clock, 32-bit value, stream.h; the 34 pins do not fit), a planar
  chunk type, a header marker for the two-stream layout, and a reader that
  merges the byte stream and the events back to 64-bit samples. Clock
  regeneration works unchanged. `EVNT` is forbidden by the v2 rule above for
  `sample_bits > 32`, so this alternative needs that rule relaxed for a
  64-bit-value variant.
- Reader cost: every sampler reads per-sample bytes instead of runs, so
  walking a long static stretch is slower than skipping a run (my reasoning, not a
  measurement).

`RUNS` can ship first; planar is additive and can be added in a later
version only if measured need appears.

### B. Keep `RLE ` and add only 64-bit runs

An `RLE64` with `u64 value, u64 run` (16 bytes a pair, fixed):

- 16 / 7 = 2.29x to 16 / 7.5 = 2.13x larger per run than `RUNS` before
  compression (my arithmetic). At the fastest simulation, 2 runs per clock:
  147.5 MB/s encoded, against 64.5-69.2 MB/s (my arithmetic). Compression
  cost scales with input bytes: 14.8-29.5% of a core at 1-0.5 GB/s, against
  the spec's 4-14% (my arithmetic: 147.5 / 1000 and 147.5 / 500).
- It does not help the board: a 16-byte pair is worse than `RLE `'s 8, which
  the rle-note found only +12% over `RAW `. The compact-RLE question would
  stay open, and a second new chunk would be needed for it.
- Smaller change in the reader (fixed-size pairs, no LEB128 decoding). The
  size and board costs above outweigh that.

## Recommendation

Adopt `RUNS` with the header extensions as proposed. It answers the
compact-RLE question with the one chunk, serves the simulation trace
unchanged, keeps `RLE ` for existing data, and leaves planar as a
measured-need follow-up.

## Open points for the decision

- Reader error handling: a pair with bits at or above `sample_bits` set, a
  non-minimal LEB128, or a chunk length not matching exactly is a malformed
  chunk. The note does not say whether the reader errors or resyncs
  (stream.h's reader resyncs on framing errors, errors on others); the
  implementation plan (Tasks 5-9) picks, matching existing behaviour.
- `desc` stays at most 255 bytes (stream.h `VGACAP_DESC_MAX`); long
  provenance goes in `META`, which holds up to 4096 bytes.
