# Final review — Milestone 2: stream format and reconstruction library

Range `61cd594..e1aab07` (25 commits, `main`). Read via the packaged diff
(`review-61cd594..e1aab07.diff`, all 2284 lines are additions, so the merged
sources were read directly rather than as hunks), the plan
(`docs/superpowers/plans/2026-09-15-m2-stream-and-frame.md`), spec §5.1/§5.2/§8,
and the round-1 report (`task-6to8-review.md`).

Verified by running, in a throwaway build directory outside the repo
(`build-final/`, deleted afterwards; working tree, index and HEAD untouched,
`git status` clean):

- `cmake -S . -B build-final && cmake --build build-final` — clean under
  `-Wall -Wextra -Werror -Wshadow -Wconversion`, no warnings.
- `ctest` — 8/8 pass. `uv run pytest -q` — 19/19 pass.
- Four targeted probes against the built library and the two CLIs (throughput,
  a dropped byte, a malformed `TIME` chunk, a FRAM→RAW mixed stream). Each is
  quoted with its result below.

---

## Strengths

**The tests verify behaviour, not shape.** `tests/test_frame.c:39-42` and
`tests/test_frame_partial.c:26-29` compare *every pixel* of the reconstruction
against the generator, and `python/tests/test_frames_e2e.py:44-56` drives the
real `vgacap-frames` binary over 3 modes × 3 chunk encodings and compares the
PPM to a numpy reference with `assert_array_equal`. Two independent generators
(`tests/synth.c`, `python/vgacap/synth.py`) are pinned against each other
(`test_bars_matches_c_bars_formula`). This is the level of rigour that makes the
x/y-alignment claims checkable rather than asserted, and it is why I could spend
my time on the architecture instead of re-deriving the crop arithmetic.

**Every round-1 finding was fixed, and each fix carries a regression test that
encodes the reasoning.** C1 → `oversized_run_does_not_overflow`
(`test_frame.c:70-83`); I1 → `force_mode_wider_than_buffer_emits_nothing`
(`:85-102`); I3 → `fram_flush_clears_stale_rows` (`test_frame_partial.c:90-108`);
I2 → `windows_reassemble_without_force_mode` (`:32-65`); M1 →
`locks_from_a_stream_that_starts_mid_frame` (`test_timing.c:53-77`) plus
`converges_from_a_mid_frame_start` (`test_frame.c:104-131`); M12 → the
`out_timing` snapshot (`frame.c:103-117`) with two tests pinning the reported
mode *and* polarity. I re-checked the memory-safety fixes by reading the code:
`frame.c:162` cannot wrap, `frame.c:90` bails before the clamps, and every
`raw`/`rgb` index in `emit()` is bounded by the clamped `w`/`h`. I found no
remaining out-of-bounds path in either library.

**The run-based decoder is the right abstraction, and it pays off measurably.**
`src/frame/frame.c` never learns which chunk type produced a sample; `RAW`,
`RLE`, `FRAM` and `EVNT` all collapse to `(value, run)`. Measured on 20 frames
of 640×480@60 (8.4 M samples):

```
RAW  8.4 MB  0.12 s   ~70 Msample/s   (~2.8× real time for 640x480@60)
RLE  5.1 MB  0.03 s  ~280 Msample/s
```

So the per-sample callback path clears real time with margin on a host, and the
RLE path — which is what a bandwidth-limited link will actually carry — is four
times cheaper again. The USB serial link at "a few MB/s" is nowhere near this
limit (uncompressed 8-bit 640×480@60 is 25 MB/s), so M3's bottleneck will be the
wire, not the decoder.

**The frame layer is self-healing, which is the property that matters on a lossy
link.** I deleted one byte from the middle of a 20-frame RAW stream. The
container framing never recovers (see I1), but every frame that *is* emitted is
still pixel-exact:

```
$ vgacap-frames dropped.vgacap out/drop   # 18 frames -> 6 frames
frames=6
# all 6 PPMs vs the reference: 0 mismatching pixels
```

That is not luck in the frame layer: the learner re-derives polarity and timing
from the sync bits alone, and the emit gate (`frame.c:150`) refuses to publish a
frame that is neither locked nor table-matched, so corrupted periods are dropped
rather than shown. For a GStreamer element this is exactly the behaviour you
want — glitch-free output with a reduced frame rate, not garbage frames.

**Comments explain why, not what.** `frame.c:32-37` (why `fram_cpl` is a valid
mode source), `frame.c:196-200` (why `have_prev` must be cleared *with*
`h_high`/`h_low`), `frame.c:159-161` (why the clip is written the way it is),
`timing.c:38-50` (the mid-frame-start correction). Someone picking this up in
six months can follow the reasoning.

**Constraint compliance is clean.** No allocation anywhere
(`grep -rn "malloc\|calloc\|realloc\|strdup" src/ include/ tests/` → nothing),
SPDX on every file added in this range, C99 + libc only, all buffers
caller-supplied, CI runs both suites on every push.

**Plan alignment: all ten tasks are present and complete.** Task 1 predates the
range; Tasks 2-10 are all delivered, file for file against the plan's "File
structure" list, plus `python/vgacap/modes.py` and `python/vgacap/bin2stream.py`
(both plan-sanctioned). The controller's rulings are all sound and I would have
made the same calls — in particular "runs are u32" (a header-variable run width
buys nothing and complicates every reader), "RAW words are DMA-verbatim" (the
right call: it keeps the capture side free of per-sample work), and the
`out_timing` snapshot (the only way to report a crop that the learner did not
itself derive). The "two frame periods starting mid-frame yields no complete
frame" ruling is not just acceptable, it is forced: you cannot recognise a pulse
as a pulse before you have measured its duration once, so no implementation of
this design can do better. `test_frame.c:104-118` argues exactly that, in the
test.

---

## Issues

### Critical

None. No memory-safety defect survives in this range, and both test suites pass
from clean.

### Important

**I1 — `src/stream/reader.c:166-183`: the chunk parser has no resynchronisation
and cannot even detect that it lost framing. Silent data loss on a link that
drops bytes.**

The reader trusts `length` absolutely (`reader.c:172`) and skips unknown tags
without comment (`reader.c:163`). One dropped byte therefore shifts every
subsequent tag/length pair, and because arbitrary bytes are a valid "unknown
tag", the parser wanders through the rest of the stream reporting success.
Demonstrated by deleting byte 3,000,000 of a 20-frame stream:

```
$ vgacap-dump dropped.vgacap        # mis-framed, exit 0, no diagnostic
RAW  samples=26784                  # <- desynchronised here
RAW  samples=65536
$ vgacap-frames dropped.vgacap out/drop
frames=6                            # 18 expected; exit 0
```

Two-thirds of the capture vanished and nothing reported it. Why it matters: M3
feeds this reader from a USB serial link, and the host needs to (a) recover
framing rather than lose the rest of the session and (b) *count* the loss so the
GStreamer element can report it. Today it can do neither. This is a gap in the
format as specified in the plan, not a coding error — the format has no sync
word, so recovery is not implementable without a format change.

Fix (a format decision for M3, cheap to make now while there is one writer):
add a 4-byte sync sentinel before each chunk header, or require the tag to be in
a known whitelist plus a plausibility bound on `length`; then add
`vgacap_reader_resync(r)` that rescans for a valid tag at a 4-byte boundary, and
an `VGACAP_EV_ERROR`/dropped-byte counter so the loss is visible. The `TIME`
chunk already has a `dropped_samples` field — this is the same reporting need on
the host side.

**I2 — `src/stream/reader.c:47-56`: `TIME` `msg_len` is not bounded by the chunk
payload, and no chunk validates its item count against its length.**

`reader.c:52` clamps `msg_len` to 255 but never to `length - 18`, so a `TIME`
chunk that declares 20 message bytes and carries none returns 20 bytes of
whatever was last in `msgbuf` — and `msgbuf` is also the scratch buffer for the
VGCH header parse (`reader.c:64`). Demonstrated:

```
TIME msg_len=20 msg=[01000803 efbeadde 0703000401050206 04000000]
feed -> 0                           # accepted, no error
              ^^^^^^^^ = the VGCH header: version, sample_bits, clock_hz, signal_map
```

No out-of-bounds read (the buffer is `char[256]`, zeroed at init), but a
consumer that prints or forwards `msg` emits stale binary from the same stream,
and the malformed chunk is accepted silently. The same class of gap applies to
every other chunk: `RAW`/`FRAM` `sample_count`, `RLE ` `pair_count` and `EVNT`
`event_count` are never cross-checked against the payload length
(`reader.c:25-37` only checks a minimum), so a corrupt count silently truncates
or pads the sample sequence instead of failing. This is spec §8's "fuzzed
lengths" row, which the plan's self-review deferred to Milestone 4 — that was
reasonable when the input was a file written by our own writer; it is not once
the input is a serial link.

Fix: clamp `ml` to `r->length - 18` in `end_payload`; and in `begin_payload` (or
as soon as the count field is parsed) require the declared count to be
consistent with the remaining payload, `fail()` otherwise.

**I3 — `src/frame/frame.c:138,187`: `fram_mode` latches for the lifetime of the
object, so continuous chunks arriving after any FRAM chunk are silently
discarded.**

Nothing ever clears `fram_mode`. Once set, `r == 2` is ignored (`frame.c:138-142`)
and the only emit path is `fram_remaining == 0 && covered(f)`, which cannot be
re-armed by non-FRAM data. A stream of FRAM windows for one frame followed by
three full frames of RAW:

```
$ vgacap-frames mixed.vgacap out/mix
frame 0: 640x480 mode=640x480@60 cpl=800 lpf=525 hsync=neg vsync=neg partial=0
frames=1                            # the three RAW frames are gone; exit 0
```

Why it matters: M3's capture firmware is specified to produce *both* `RAW` and
`FRAM` chunks (spec §5.3: streaming ring buffers *and* `sample_frame` windowed
capture), so a firmware that switches capture mode mid-session — or a host that
concatenates two captures — silently stops producing pictures. Fix: leave FRAM
mode when a run arrives with `fram_remaining == 0` and no FRAM chunk is open, or
expose an explicit mode reset (see I4).

**I4 — `include/vgacap/frame.h:60-66,97`: the output API will need to change for
the GStreamer element; changing it now costs two call sites, later it costs
three plus a plugin.**

Three specifics, all cheap today:

1. *The rgb buffer is owned by `vgaframe_t` and reused* (`frame.c:119`:
   `out.rgb24 = f->rgb`). It is valid only until the next `emit`, but unlike
   `u.time.msg` (documented at `stream.h:120`) nothing says so. A GStreamer
   element cannot hand that pointer to a `GstBuffer`; it must memcpy every
   frame (~900 KB, ~55 MB/s at 60 fps — survivable, but pointless). Let the
   caller supply the next rgb buffer (a `vgaframe_set_rgb_buffer()` called from
   inside the callback, or a "get next buffer" callback) so the element can
   hand over pool memory directly.
2. *No stride.* Rows are packed at exactly `width * 3`. GStreamer's
   `GST_VIDEO_FORMAT_RGB` wants rows padded to a 4-byte boundary, so every
   width not divisible by 4 needs a per-row copy. A `stride` field in
   `vgaframe_config_t` costs one multiply in `emit`'s inner loop.
3. *No reset.* `vgaframe_init` happens to work as one (it memsets the struct and
   the buffers, and the buffers are caller-owned), but nothing says so, and it
   is the only way to clear `fram_mode` (I3), to recover after a stream
   discontinuity, or to handle a GStreamer flush/seek/reconnect. Either document
   `vgaframe_init` as the reset or add `vgaframe_reset(f)`.

Integer widths, checked: `width`/`height` as `uint16_t` and `frames_seen` as
`uint32_t` are fine; `run` as `uint32_t` is fine; `max_clocks_per_line`/
`max_lines` as `uint16_t` are fine. The one real width bug is m9 below.

### Minor

- **m1 — `src/frame/frame.c:166`** `f->x += run` can itself wrap for a
  near-2³² run, bringing `x` back under `W` and letting the *next* push write
  pixels at a bogus column. No out-of-bounds access (the clip at `:162` is
  wrap-free), just a wrong picture. Saturate: `f->x = (run > UINT32_MAX - f->x) ? UINT32_MAX : f->x + run;`
- **m2 — `src/frame/frame.c:150`** when `r == 2` arrives and the gate rejects the
  frame, `raw`/`cover` are not cleared (clearing happens only inside `emit`).
  Harmless while a full frame overwrites every row it uses; stale tail rows
  survive a change to a shorter mode. Clear on the reject path too.
- **m3 — `src/frame/frame.c:72-85`** the auto-crop bounding-box branch — the
  CLI's only fallback for an unknown mode — still has no test.
  `table_match_wins_over_odd_porches` exercises the table path, and
  `mode_match_trusted_over_disagreeing_measurement` never emits the unmatched
  frame. A synthetic mode with a (cpl, lpf) off the table would close it.
- **m4 — `src/tools/vgacap_dump.c:83-85, 33, 57-61`** three related gaps: a
  truncated unknown chunk returns exit 1 with nothing on stderr while every
  other tag prints an error; the `while (fread(head,1,8,fp) == 8)` loop treats a
  trailing 1-7 byte fragment as a clean end of file; and the `RLE ` pair loop
  reads `pairs` pairs without bounding them by `length`, so a bogus count walks
  into the following chunks.
- **m5 — `src/stream/writer.c:35` and `src/stream/reader.c:12`** `sample_mask()`
  is duplicated verbatim. Three lines, two translation units, no shared internal
  header yet — real but trivial.
- **m6 — `src/tools/vgacap_frames.c`** `:84-91` pushes runs with no `have_header`
  guard (safe only by accident — `f->y < max_lines` is false on a zeroed
  struct); `:49` ignores `snprintf` truncation, so a long prefix makes every
  frame overwrite one file; `:147-148` flushes unconditionally at EOF, so a
  stream that ended on a complete frame emits one extra all-magenta partial
  (written as a garbage PPM under `--partial`).
- **m7 — `src/frame/frame.c:22-30`** `vgaframe_init` does not check that the
  forced or expected mode fits `max_clocks_per_line × max_lines`; wider lines are
  silently truncated (`:158-165`) and the crop silently narrows (`:91-92`).
  Worth a return code or at least a sentence in `frame.h`.
- **m8 — `include/vgacap/frame.h:51,88`** `h_edge_count`, `fram_first_line` and
  `fram_line_count` are written and never read. `fram_cpl` is now used, so this
  is the residue.
- **m9 — `src/stream/reader.c:142`** `(uint32_t)(clk - r->last_event_clock)`
  truncates silently when two EVNT timestamps are more than 2³² clocks apart
  (~171 s at 25 MHz) — a plausible gap for a simulator trace of a static image.
  Split into multiple runs or clamp and report.
- **m10 — `python/vgacap/bin2stream.py:2`** the docstring offers "one sample per
  byte or per 32-bit word"; only bytes are implemented.
- **m11 — `python/vgacap/stream.py:95-100`** `parse_header` is laxer than the C
  reader: it does not check `desc_len` against the payload, nor validate
  `sample_bits`/`samples_per_word`. The mirror therefore accepts streams the C
  reader rejects, which weakens it as a cross-check.
- **m12 — `tests/test_stream_chunks.c:7-9`** `msgs[4096][64]` is memcpy'd with
  `msg_len` (up to 255). Test-only and never triggered today, but it is a buffer
  overflow waiting for the first long-message test.
- **m13 — `include/vgacap/frame.h:61`** `rgb24`'s lifetime is not documented
  (contrast `stream.h:120`, which does document `msg`'s). See I4.
- **m14 — `src/tools/vgacap_frames.c:14-15`** `MAX_CPL`/`MAX_LINES` are hardcoded
  at 1400×900 and there is no `--force-mode`. Fine for the built-in table (max
  1344×806), but the tool cannot be pointed at anything larger, and the
  FRAM-without-a-table-mode path has no way to be told the geometry.

---

## Triage of the deferred minors

| Item | Verdict |
|---|---|
| (a) `reader.c` TIME `msg_len` unchecked against payload length | **Fix now** — promoted to I2; confirmed by probe that it leaks the parsed VGCH header bytes, and the same validation gap covers every other chunk's item count. Two lines for the clamp, a few more for the count checks. |
| (b) `vgacap-dump` returns silently on a truncated unknown chunk | Later — tool-only cosmetics; fold into m4 with the two related dump gaps. |
| (c) `sample_mask()` duplicated in `writer.c`/`reader.c` | Later — three lines across a library boundary; introduce a `src/stream/internal.h` when a second shared helper appears, not before. |
| (d) M1 first-frame bogus `lines_per_frame` | Already fixed (`timing.c:38-51`) and tested. |
| (d) M2 `-Wconversion`-unsafe ternary in `bit()` | Already fixed (`frame.c:10-14`). |
| (d) M3 dead branch in the FRAM flush | Already fixed (`frame.c:185`). |
| (d) M4 stale comments in `test_frame.c` | Already fixed (`test_frame.c:55-58`). |
| (d) M5 auto-crop branch untested | Later — m3 above. Do it before anything depends on auto-crop; the CLI's unknown-mode path is untested today. |
| (d) M6 skipped emit leaves `raw`/`cover` uncleared | Later — m2 above. |
| (d) M7 unused FRAM metadata | Later — m8 above; `fram_cpl` is now used, the rest is cosmetic. |
| (d) M8 no `have_header` guard in `vgacap-frames` | Later — m6 above; the reader guarantees header-first today, so this is defensive only. |
| (d) M9 silent truncation when a mode exceeds the buffer | Later — m7 above; document in `frame.h` at minimum. |
| (d) M10 `snprintf` truncation ignored | Later — m6 above. |
| (d) M11 unconditional flush at EOF | Later — m6 above. |
| (d) M12 `out.timing` always the learner's | Already fixed (`frame.c:103-117`, `out_timing`), with two regression tests. |

Only **(a)** must be fixed before Milestone 3. Everything else in the deferred
list is safe to carry.

---

## Recommendations for Milestone 3

1. **Decide the framing-recovery story before writing the capture firmware**
   (I1). It is a format change — a sync sentinel or a tag whitelist plus a length
   bound — and it is far cheaper now, with one writer and one reader, than after
   a Pico firmware and a GStreamer plugin are both emitting and consuming the
   format. Ship `vgacap_reader_resync()` and a loss counter with it, and add the
   "fuzzed lengths" test from spec §8 at the same time rather than in M4: a
   corpus of streams with flipped/deleted/inserted bytes, asserting that the
   reader either recovers or errors, and never reports success on a stream it
   mis-parsed.
2. **Settle the output API before wrapping it in GStreamer** (I4): caller-supplied
   rgb buffer, a stride field, and a documented reset. Three small changes to one
   header while there are two call sites.
3. **Unlatch FRAM mode** (I3) — the firmware is specified to produce both chunk
   families, so a mixed stream is the expected case, not an edge case. Add the
   mixed-stream case to the e2e test matrix (`write_stream` already has the
   pieces: write FRAM windows and then RAW chunks into one file).
4. **Give `vgacap-frames` a `--force-mode` and buffer-size options** (m14). The
   FRAM-without-a-table-mode path currently depends on `vgaframe_mode_match_cpl`
   succeeding; when a project runs a non-VESA timing — which Tiny Tapeout
   projects do — there is no way to tell the tool the geometry, and m3's untested
   auto-crop is all that stands behind it.
5. **Add a wall-clock/frame-count timeout for FRAM accumulation.** Spec §5.2 asks
   for "emits when coverage is complete, **or on a timeout** with a partial flag".
   What exists is a counter-change flush plus `vgaframe_flush`, which is
   sufficient for a file but not for a live element whose source stalls
   mid-frame. The plan never carried the timeout clause forward, so this is a
   plan omission rather than an implementation miss — but M3 is where it bites.
6. **Throughput is not a concern; do not optimise it speculatively.** 70 Msample/s
   on the RAW path is ~2.8× real time for 640×480@60 and the link will cap out
   an order of magnitude below that. If a bulk API is ever wanted, the shape is
   `vgaframe_push_runs(f, const uint32_t *values, const uint32_t *runs, size_t n)`
   — but measure first.
7. **Consider running CI with `-fsanitize=address,undefined`** on the C suite.
   Round 1 found two out-of-bounds writes that ASan caught instantly and
   `-Werror` did not; the suite runs in 0.13 s, so a second sanitized job is
   nearly free and would have caught both before review.

---

## Assessment

**Ready to merge? With fixes.**

The milestone is done and done well. Every plan task is delivered, the deviations
and controller rulings are sound (and in the mid-frame-start case, provably
forced), the constraints are honoured without exception, both suites pass from
clean under an aggressive warning set, and the tests are genuinely pixel-exact
across two languages and two binaries rather than shape-checking. Every finding
from the round-1 review was fixed properly, with a regression test each that
records the reasoning. I found no memory-safety defect and no incorrect output on
well-formed input.

The work is already on `main` and should stay there — nothing here justifies a
revert. What it needs before Milestone 3 layers on top:

- **I2** (clamp `TIME` `msg_len`, validate chunk item counts) — a small, local
  fix; do it first because it is unambiguous.
- **I1** (chunk-framing resync) and **I4** (output API shape) — both are
  *decisions* more than code, and both get more expensive the moment a Pico
  firmware and a GStreamer plugin depend on the current shapes. Make them at the
  start of M3, not at the end.
- **I3** (FRAM mode latch) — a handful of lines plus a test; the mixed stream it
  breaks is the expected M3 output, not a corner case.

Of the deferred minors, only (a) must be fixed now; it is folded into I2. The
rest can ride along.
