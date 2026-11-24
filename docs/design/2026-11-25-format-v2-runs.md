# VGCH format v2: wide samples, a `RUNS` chunk and a trace container

Date: 2026-11-25.

Status: decided 2026-11-25 (decision 1 of the tinytapeout-vga-videos spec).
The decisions are listed in one place, with
recommendations, in "Decisions for Tim" at the end.

Decision (2026-11-25): Tim left (a)-(c) to the recommendations, which are adopted: RUNS; board adoption decided after Milestone 10; skip-by-length.

Amended 2026-11-25 during implementation review (controller's Ruling K): which losses make n unknown; the discard report string; `skipped` for a skip by length.

Sources, cited by short name below:

- **spec**: `tinytapeout-vga-videos/docs/superpowers/specs/2026-11-24-raw-frames-and-hash-methods-design.md`
  (sections "Layer 1: the trace", "Performance budget", "Shared code: vgacap").
- **vgacap**: github.com/mithro/vgacap at commit 5d84564, the base of the
  Milestone 10 stack. Every file:line below was checked in the worktree
  `vgacap/.worktrees/m10-third-party`, which is 5d84564 plus vendored
  third-party code only (HEAD 6c0e45f). **stream.h** is
  `include/vgacap/stream.h`; **reader.c** and **writer.c** are
  `src/stream/`; ttcap is `python/ttcap/`.
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
   the rtl-note). The rle-note's figures per 16,384-sample buffer on the
   RP2350 are: `RAW ` 23.4 ms (700 k samples/s), `RLE ` as specified 20.9 ms
   (784 k, +12%), a compact pair of about 3 bytes (u8 value + LEB128 run)
   11.2 ms (1.46 M, 2.1x). **The compact row is an estimate, not a
   measurement**: it reuses the u32 encoder's 5.4 ms and a computed send
   time, and a LEB128 encoder was never run on the board. The `RLE ` row's
   encode time is measured.
   The rle-note recommends the compact chunk and says the RTL encoder
   should emit the same chunk.

**Answer to the compact-RLE question: yes, and it is the same chunk.** The
board's pair is a `RUNS` chunk with a board profile's `sample_bits`; a pair
is `vbytes` value bytes plus a LEB128 run. On the RP2350 profile
(`RP2350_DBV3`, `sample_bits` 8, ttcap `boards.py:67-78`) `vbytes = 1`, which
is exactly the rle-note's "u8 value + LEB128 run". The RP2040 profile
(`RP2040_TT06`, `sample_bits` 12, `boards.py:55-66`) has `vbytes = 2`. The
simulation's 43-bit pair is the same chunk with `sample_bits = 43`,
`vbytes = 6`. One chunk type, one reader path, one Python mirror, and the
RTL encoder (rtl-note) emits the same thing as the board. `RLE ` stays
readable in version 1 streams (existing captures, and the `pio-rle`
firmware that emits it, spec "Shared code"); a version 2 stream never carries
it (see "One representation").

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
  `sample_bits > 32`. For `sample_bits <= 32` the version 1 rules for
  `samples_per_word` are unchanged.

Then four new bytes:

| offset | type | field |
|---|---|---|
| 20 | u8 | `samples_per_clock`: 1 or 2 (1 for board captures) |
| 21 | u8 | `clock_bit`: 0..63, or 0xFF for none |
| 22 | u8 | `clock_first`: 0 or 1, the clock bit's value in sample 0 |
| 23 | u8 | reserved, must be 0 |

Then `desc_len` bytes of description. **In version 2 `desc_len` is at most
251**, so the chunk length is `24 + desc_len`, at most 275. The reason: a
version 1 reader accepts a VGCH length of 20 to `20 + VGACAP_DESC_MAX` =
275 only (reader.c:60). A longer version 2 header would be rejected by it as
"bad VGCH length" before its version check (reader.c:118), which then
reports "chunk before header" for everything after. At 275 or less a
version 1 reader always reaches its "unsupported version" error. (Version 1's
`desc_len` limit of 255, `VGACAP_DESC_MAX` in stream.h:24, is unchanged.)

Validity rules:

- `samples_per_clock == 2` if and only if `clock_bit != 0xFF`. The two
  conditions are equivalent; either one alone is "bad VGCH v2 clock fields";
- `clock_first` must be 0 when there is no clock bit;
- in every value, bits at or above `sample_bits` must be 0, so each value
  has one encoding;
- `desc_len <= 251`.

A header is invalid, and the reader rejects it by resynchronising, as for
other bad VGCH fields, for each of:

| invalid header | `what` string |
|---|---|
| `desc_len` above 251 (chunk length above 275) | "bad VGCH length" |
| `sample_bits` outside 1..64 | "bad sample_bits" |
| `samples_per_word` not 0 when `sample_bits > 32`, or, when `sample_bits <= 32`, outside the version 1 rules | "bad samples_per_word" |
| `samples_per_clock` not 1 or 2 | "bad VGCH v2 clock fields" |
| `clock_bit` neither below `sample_bits` nor 0xFF | "bad VGCH v2 clock fields" |
| `samples_per_clock == 2` with no clock bit, or a clock bit with `samples_per_clock != 2` | "bad VGCH v2 clock fields" |
| `clock_first` above 1, or non-zero with no clock bit | "bad VGCH v2 clock fields" |
| reserved byte 23 not 0 | "bad VGCH v2 clock fields" |

("bad sample_bits", "bad samples_per_word" and "bad VGCH length" are the
strings the reader already uses, reader.c:60, 123, 125.)

A version 1 header reads as `samples_per_clock = 1`, `clock_bit = 0xFF`,
`clock_first = 0`. A version 2 reader treats a version of 0 or 3 and above
as "unsupported version", a fatal error, as today (reader.c:118). It reads
version 1 streams unchanged.

Compatibility: today's reader rejects any version other than 1 (reader.c:118),
so a version 1 reader fails cleanly on a version 2 header instead of
misreading it.

### Which chunks a header allows

Today's readers silently skip a chunk with a tag they do not know: the C
reader's `payload_byte` ends `return 0; // skip unknown` (reader.c:245) and
Python's `read_stream` has no `else` branch for an unknown tag
(`python/vgacap/stream.py`, the `if/elif` chain in `read_stream`). **A
version 1 reader (today's code) therefore skips `RUNS`, `BLKH` and `META`
without notice**: a board stream of `RUNS` under a version 1 header reads as
success with zero samples. That is why a version 2 stream must not be given
a version 1 header, and why:

- **`RUNS`, `BLKH` and `META` are allowed only after a version 2 header.** A
  version 2 reader that meets one in a version 1 stream skips it by its
  length and reports `what = "chunk needs a version 2 header"` (reporting
  rule below).
- **One representation: a version 2 stream never carries `RLE `.** Version 2
  run data is `RUNS` only. A `RLE ` chunk in any version 2 stream is skipped
  by length with `what = "RLE  chunk not allowed in version 2"` (two spaces,
  the tag's own trailing space).
- `RAW `, `FRAM` and `EVNT` stay allowed in version 2 streams with
  `sample_bits <= 32` and no clock bit. With `sample_bits > 32` and no clock
  bit they are skipped with `what = "chunk not allowed with sample_bits over
  32"`; with a clock bit, with `what = "chunk not allowed with a sample
  clock"` (the clock-bit check applies first). `EVNT`'s `u64` is a sample
  index and, since a clock bit forbids it, it can appear only in
  `samples_per_clock == 1` streams.
- A stream with a clock bit may contain only `RUNS`, `BLKH`, `META` and
  `TIME` chunks; any other chunk type is skipped with `what = "chunk not
  allowed with a sample clock"`.
- `TIME` is allowed everywhere, as today.

### `RUNS`

Payload: `u32 pair_count`, then `pair_count` pairs. `pair_count` is at least
1: a `RUNS` chunk with `pair_count == 0` is malformed
(`what = "RUNS has no pairs"`). Each pair is:

- `value`: `vbytes = ceil(sample_bits / 8)` bytes, little-endian, with the
  clock bit stored as 0. A stored value with the clock bit set is
  malformed (`"RUNS value has the clock bit set"`), and so is one with a bit
  at or above `sample_bits` set (`"RUNS value has bits above sample_bits"`);
- `run`: LEB128 u64, at least 1 (`"RUNS run is zero"`), at most 10 bytes
  with the 10th byte at most `0x01` (`"RUNS run over 64 bits"`), and
  minimally encoded: the last byte is non-zero unless the whole value is 0,
  which a run never is, so `80 00` and `81 00` are both non-minimal
  (`"RUNS run not minimally encoded"`).

Two adjacent pairs inside one `RUNS` chunk must differ in value
(`"RUNS adjacent pairs have equal values"`). Equal values in adjacent pairs
across a chunk boundary are allowed: a writer may split a run at buffer ends,
and the trace writer splits at block ends. Readers must not assume runs are
maximal across chunks.

The chunk length must equal `4 +` the pairs' bytes exactly
(`"RUNS pairs do not fill the chunk"`). A pair is `vbytes + 1..10` bytes: 7
to 16 bytes at 43 bits, 2 to 11 at 8 bits. Because pairs are variable-size,
`pair_count` no longer fixes the chunk's length, as it does for `RLE `'s
fixed 8-byte pairs. The rtl-note's fixed-N idea (a known count means a known
length up front) therefore does not carry over; what holds instead is that
the reader checks the pairs fill the declared length exactly, and a writer
that streams must still know the chunk's byte length when it writes the
chunk header, by buffering the chunk.

#### The sample index `n` and clock regeneration

`n` is the sample index of the next sample the reader will deliver:

- `n = 0` immediately after the VGCH header.
- `n` advances by every sample any chunk delivers, across all chunks:
  `RUNS`, and in the streams that allow them, `RAW `, `FRAM` and `EVNT`.
- A `BLKH` sets `n = first_sample` (below).

The reader sets the clock bit of each run's value to
`clock_first ^ (n & 1)`, where `n` is the run's first sample. The run event
therefore carries the full value of the run's first sample, and the clock
bit of every later sample in the run is that value's clock bit toggled each
sample (spec, "Shared code", row 1; "The clock in a run-encoded trace"). With
no clock bit, the value is used as stored.

The run event counts *samples*, not clocks. With `samples_per_clock == 1` a
sample is a clock; with 2 a clock is two samples. The comment on
`VGACAP_EV_RUN` in stream.h:125 says "clocks" and is corrected to
"samples".

After a reported loss that could have carried samples, in a stream with a
clock bit, `n` is unknown. Those losses are: a byte-wise resync; a `RUNS`
content error; a bad `BLKH`; a forbidden `RAW `, `FRAM`, `EVNT` or `RLE `
chunk; and an unknown tag (a clock stream forbids these, and they could be
samples). A `META` skipped for "bad META length" or "bad META text" carries no
samples and leaves `n` known. A well-formed `TIME` chunk never affects `n`.
A bad `TIME` (a version 1 chunk, recovered by a byte-wise resync) leaves `n`
known only when the scan regains framing exactly at that `TIME` chunk's end
(8 + its declared length), which proves only the `TIME` was lost; otherwise
`n` is unknown. Two independent faults can defeat this check (a `TIME`
whose length is raised to cover the next chunk, and that chunk's tag also
destroyed); that is the same exposure as any consistently corrupted
length. While `n` is unknown the
reader discards runs without delivering them until the next `BLKH`, and
counts them in the loss report, so a lost chunk never gives later runs a
wrong clock bit. (The `BLKH` gap report below is the one exception:
it reports and adopts `first_sample` in the same step, so `n` is known
again at once.) Streams without a clock bit are unaffected.

### `BLKH`

Payload: `u64 first_sample`, the sample number of the block's first sample,
exactly 8 bytes (`"bad BLKH length"` otherwise). It sets `n = first_sample`.

- `BLKH` is allowed in any version 2 stream, and is required only in trace
  containers, where it is each block's first chunk.
- A reader reading sequentially that meets a `BLKH` whose `first_sample`
  differs from its running `n` reports
  `what = "BLKH first_sample does not follow"` (a gap or an overlap), then
  adopts `first_sample`.
- A reader positioned at a block by a seek starts from that block's `BLKH`
  and reports nothing.

### `META`

Payload: 1..4096 bytes (`"bad META length"` otherwise) of UTF-8 text,
`key=value` lines, each ending `\n`. Value syntax is everything after the
first `=` up to `\n`. The text is malformed (`"bad META text"`) if it is not
UTF-8, its first line is not `meta=open` or `meta=close`, it lacks a final
`\n`, a line has no `=`, a key repeats, or a key does not match
`[a-z][a-z0-9_]*`.

- `meta=open` requires `project`, `calib_seconds`, `seconds` and `layout`.
  It may carry `override`, `simulator` and `harness`. The clock is the
  header's `clock_hz` alone.
- `meta=close` requires `capture_after_clock`, `status` and `frames`.
- Unknown keys are allowed and ignored, so later versions can add keys.

Value syntax, and meaning (the keys' meanings are the spec's: spec lines
305-313, the sampler's parameters, for the opening keys; lines 388-394 and
536-545, `capture_after_clock` and `status`, for the closing keys):

| key | value |
|---|---|
| `capture_after_clock`, `frames` | unsigned decimal integer |
| `calib_seconds`, `seconds` | decimal number as C `strtod` reads it in the C locale |
| `status` | one of `ok`, `sim-timeout`, `unstable-sync`, `no-sync`, `bad-timing` |
| `layout` | one of `tt-um-43` |
| `project`, `override`, `simulator`, `harness` | free text |

(`status` values are those the spec names, at its lines 394, 788, 828-831 and
892; a trace cut short has no closing chunk and the spec treats its status
as `truncated` (line 541), which is therefore never written.)

`layout=tt-um-43` names the 43-bit sample layout (spec, "What is recorded":
`uo_out` bits 0-7, `uio_out` 8-15, `uio_oe` 16-23, `ui_in` 24-31, `uio_in`
32-39, `rst_n` 40, `ena` 41, `clk` 42). It **requires** `sample_bits = 43`,
`samples_per_clock = 2`, `clock_bit = 42` and `clock_first = 0`. A tool that
reads the layout (`vgacap-sample`, `vgacap-export`) rejects a trace whose
header disagrees. The header is authoritative for decoding; the layout only
names the pins. Because `uo_out` is the low byte, the header's `signal_map`
can carry the ordinary Tiny VGA map `{7,3,0,4,1,5,2,6}` unchanged (spec,
"What is recorded").

### Container

A trace file is zstd's seekable format (spec, "Size and format"). Each zstd
frame is one block. The seek table is a skippable frame at the end, so plain
`zstd -d` yields the whole VGCH stream.

- Block 0 is `VGCH`, `META(open)`, `BLKH(0)`, then `RUNS`. Every later block
  is `BLKH(first)`, then `RUNS`.
- The last block ends with `META(close)`.
- A block closes before its uncompressed size would pass 16 MiB minus
  64 KiB, or at 2^24 clocks counted from the block's first sample
  (`2^24 * samples_per_clock` samples after its `BLKH`, not at absolute
  multiples). A run that would cross the boundary is split.

The 16 MiB bound is `VGACAP_MAX_CHUNK_LEN` (stream.h:33); the 64 KiB margin
leaves room for the chunk headers, `BLKH` and `META(close)`. At 7 bytes a
run, 16 MiB minus 64 KiB (16,711,680 bytes) holds at most about 2.39
million runs (my arithmetic: 16,711,680 / 7).

## Reader rules for malformed and disallowed chunks

For the three new chunk types, and for chunk types that a header forbids, a
known tag with a plausible length (at most `VGACAP_MAX_CHUNK_LEN`) is
trusted for framing. A content error **skips the rest of the chunk by its
length**; it never starts a byte-wise resynchronisation, because a byte-wise
search inside a payload of up to 16 MiB could match a false tag. The loss is
reported with the existing non-fatal `VGACAP_EV_RESYNC` event
(stream.h:`vgacap_event_t.u.resync`): `skipped` holds the bytes skipped and
`what` holds the string; the meaning is "data lost, framing kept". Existing
version 1 chunk handling is unchanged.

| condition | `what` |
|---|---|
| `RUNS`, `BLKH` or `META` after a version 1 header | "chunk needs a version 2 header" |
| `RLE ` in any version 2 stream | "RLE  chunk not allowed in version 2" |
| `RAW `, `FRAM`, `EVNT` with `sample_bits > 32` and no clock bit | "chunk not allowed with sample_bits over 32" |
| any chunk but `RUNS`, `BLKH`, `META`, `TIME` with a clock bit | "chunk not allowed with a sample clock" |
| `RUNS` value has the clock bit set | "RUNS value has the clock bit set" |
| `RUNS` value has bits above `sample_bits` | "RUNS value has bits above sample_bits" |
| `RUNS` run is 0 | "RUNS run is zero" |
| `RUNS` run not minimally encoded | "RUNS run not minimally encoded" |
| `RUNS` run over 64 bits | "RUNS run over 64 bits" |
| `RUNS` pairs do not fill the length exactly | "RUNS pairs do not fill the chunk" |
| `RUNS` with `pair_count == 0` | "RUNS has no pairs" |
| adjacent equal values inside one `RUNS` chunk | "RUNS adjacent pairs have equal values" |
| `BLKH` length not 8 | "bad BLKH length" |
| `BLKH` `first_sample` differs from the running `n` | "BLKH first_sample does not follow" |
| a `RUNS` chunk discarded while `n` is unknown (reported once for each chunk discarded) | "RUNS discarded: sample position unknown until BLKH" |
| `META` length 0 or above 4096 | "bad META length" |
| `META` text malformed | "bad META text" |

For a skip by length, `skipped` is 8 + the chunk's length (the chunk header
and payload), even when some of its pairs were already delivered before a
mid-chunk error.

Header faults use the table under "VGCH version 2" instead: they are
rejected as other bad VGCH fields are, since without a good header nothing
after it can be decoded.

### API changes this implies

- `vgacap_event_t.u.run` becomes a 64-bit value and a 64-bit run (spec,
  "Shared code", row "64-bit values and long runs through the API"): an ABI
  change to the `uint32_t value, run` of stream.h:136.
- Two new reader events, `VGACAP_EV_BLOCK` (a `BLKH`: its `first_sample`)
  and `VGACAP_EV_META` (a `META`: its text, valid during the callback).
- Every consumer of reader events changes:
  - `gst/gstvgadecode.c:465-466` (the `VGACAP_EV_RUN` case: advances
    `clock_pos` by `run` and calls `vgaframe_push` with 32-bit arguments);
  - `src/tools/vgacap_frames.c:102` (the `VGACAP_EV_RUN` case, same push);
  - `src/tools/vgacap_dump.c:103-107` (the run hash takes the value as 32
    bits and loops over `run` as `uint32_t`).
- `vgacap_dump.c`'s first pass (lines 37-49) does not check the version, so
  on a version 2 header it would print the four new header bytes as the
  description. It must read the version and, for 2, the new fields.
- The `VGACAP_EV_RUN` comment in stream.h:125 is corrected from "clocks" to
  "samples" (see above).
- A board writer, to emit `RUNS`, must change: the host header writer
  (ttcap `capture.py:791` writes `version=1`); ttcap's chunk whitelist
  (`repl.py:33`, `CHUNK_TAGS`, which would raise `ReplFramingError` on
  `RUNS`); firmware `PROTOCOL.md` and the mpy module. The RTL framer
  (`rtl/vgacap_raw_framer.py`) emits only `RAW `/`TIME` and is unaffected.
  **Adopting `RUNS` on boards is a later decision, outside Milestone 10**;
  this note only guarantees the chunk can serve them.

## Worked example

A 43-bit stream: the header, then one `RUNS` chunk of two pairs. There is no
`BLKH`: this is a plain stream, not a trace container, so `n = 0` comes from
"immediately after the VGCH header".

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
`4 + (6 + 2) + (6 + 1) = 19 = 0x13`. The two values differ, as adjacent
pairs must, and `pair_count` is 2.

```
52 55 4e 53  13 00 00 00                       "RUNS", length 19
02 00 00 00                                    pair_count 2
00 00 00 00 00 03  ad 02                       value 0x030000000000, run 301
80 00 00 00 00 03  01                          value 0x030000000080, run 1
```

Decoded: `n = 0` after the header. Pair 1 covers samples 0..300; its clock bit is
`clock_first ^ (0 & 1) = 0`: first-sample value 0x030000000000. `n` is then
301. Pair 2 starts at sample 301; `n & 1 = 1`, so its clock bit is 1:
first-sample value 0x070000000080 (the added 0x0400_0000_0000 is the clock
bit). Total 59 bytes. The bytes were checked against the rules in this note
(header fields and length, value bits, minimal LEB128, adjacent values,
exact fill, clock regeneration) by a throwaway Python script that built the
stream and decoded it back independently; the script is not committed.

## Costs and the sizes behind the choice

Figures are from the spec or the rle-note unless marked as my arithmetic.

- **Pair size**, simulation (43 bits): 6 value bytes plus a 1-10 byte run.
  The spec's own estimate is 7-7.5 bytes a run ("How it is written"): runs
  up to 127 samples take a 1-byte run (7 bytes), up to 16,383 take 2 (8
  bytes).
- **Busiest designs**: the spec says up to about one run per clock, two with
  logic on both edges, so 35-70 MB/s of encoded data at the fastest
  simulation (spec, "How it is written"; 4.61 M clocks/s fastest,
  "Performance budget"). 35-70 MB/s is the spec's figure. My arithmetic, at
  4.61 M clocks/s: 1 run per clock x 7 B = 32.3 MB/s; 2 x 7 B = 64.5 MB/s;
  2 x 7.5 B = 69.2 MB/s. The spec's lower end is a little above my 32.3.
- **Board**, `RP2350_DBV3`, 8 bits: the rle-note's 1,359 pairs per
  16,384-sample buffer is 10,872 bytes as `RLE ` (8 B a pair, matches the
  note) and about 3 B a pair compact, about 4.1 KB (my arithmetic:
  1,359 x 3 = 4,077). Minimum is 2 B a pair (1,359 x 2 = 2,718). These
  compact-pair figures, and the 11.2 ms and 1.46 M samples/s above, are
  estimates (see "What is being decided"). Busy content (runs of about 1)
  expands under any RLE, so the board's per-buffer fallback to `RAW `
  (rle-note) remains; `RUNS` does not change it. On `RP2040_TT06`
  (12 bits) a pair is 3 to 12 bytes.
- **Run splitting at buffer ends**: a writer may end a `RUNS` chunk in the
  middle of a long run and begin the next with the same value (allowed
  across chunks, not within one).

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
  9.2 MB/s regardless of content (my arithmetic). That is a lower bound for
  planar: it omits the other 34 pins, stored as change events with a 64-bit
  clock and a 64-bit value, whose rate is unmeasured and is to be measured
  in rollout step 2. `RUNS` on the busiest designs is 35-70 MB/s (the
  spec's figure; my arithmetic above gives 32.3-69.2). A quiet design
  loses: `RUNS` stores nothing during long constant stretches, planar
  still stores two bytes a clock.
- Format work it adds, beyond `RUNS`: an `EVNT` with a 64-bit value (today
  64-bit clock, 32-bit value, stream.h; the 34 pins do not fit), a planar
  chunk type, a header marker for the two-stream layout, and a reader that
  merges the byte stream and the events back to 64-bit samples. Clock
  regeneration works unchanged. `EVNT` is forbidden by the rules above for
  `sample_bits > 32`, and with a clock bit, so this alternative needs those
  rules relaxed for a 64-bit-value variant.
- Reader cost: every sampler reads per-sample bytes instead of runs, so
  walking a long static stretch is slower than skipping a run (my
  reasoning, not a measurement).

`RUNS` can ship first; planar is additive and can be added in a later
version only if measured need appears.

### B. Keep `RLE ` and add only 64-bit runs

An `RLE64` with `u64 value, u64 run` (16 bytes a pair, fixed):

- 16 / 7 = 2.29x to 16 / 7.5 = 2.13x larger per run than `RUNS` before
  compression (my arithmetic). Like for like at 4.61 M clocks/s: 1 run per
  clock x 16 B = 73.8 MB/s and 2 runs per clock x 16 B = 147.5 MB/s encoded,
  against `RUNS`' 32.3-69.2 MB/s (my arithmetic, above). Compression cost
  scales with input bytes: 73.8 / 1000 to 147.5 / 500 = 7.4-29.5% of a core
  (1-0.5 GB/s), against 3.2-13.8% for `RUNS` (32.3 / 1000 to
  69.2 / 500; the spec's own figure is 4-14%).
- It does not help the board: a 16-byte pair is worse than `RLE `'s 8, which
  the rle-note found only +12% over `RAW `. The compact-RLE question would
  stay open, and a second new chunk would be needed for it.
- Smaller change in the reader (fixed-size pairs, no LEB128 decoding). The
  size and board costs above outweigh that.

## Decisions for Tim

Each with a recommendation.

- **(a) The chunk.** `RUNS` as proposed, against alternative B (keep `RLE `
  and add 64-bit runs) or alternative A (planar). Recommendation: `RUNS`.
  It answers the compact-RLE question with the one chunk, serves the
  simulation trace unchanged, is 2.1-2.3x smaller than B, and leaves planar
  as a measured-need follow-up (A is additive later). Adopted.
- **(b) Whether boards adopt `RUNS` later.** Recommendation: yes, as a
  separate decision after Milestone 10, once a LEB128 encoder has been
  measured on the board (the rle-note's compact row is an estimate). This
  note keeps the door open (the chunk, the `sample_bits = 8`/12 profiles) and
  lists the board-side changes above, but changes none of them. Adopted.
- **(c) Skip-by-length for well-framed invalid chunks.** The proposal: for
  the new chunk types and chunk types a header forbids, a known tag with a
  plausible length is trusted for framing; content errors skip the chunk by
  its length and are reported as non-fatal `VGACAP_EV_RESYNC` events, never
  a byte-wise search. Recommendation: yes, because a byte-wise search inside
  a payload of up to 16 MiB could match a false tag; the cost is that a
  corrupt length field on a known tag is trusted, as it already is for v1
  chunks by the plausibility bound. Adopted.
