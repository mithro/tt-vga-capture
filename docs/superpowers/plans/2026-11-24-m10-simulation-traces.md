# Milestone 10: simulation traces -- implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give vgacap what tinytapeout-vga-videos needs to keep a raw pin trace of every simulation and derive frames from it later. That means:
- a 64-bit run-length stream format;
- a seekable, compressed trace container written from inside `tb.cpp`;
- the shared calibration and frame clock;
- the samplers `tb-v1` and `centre-v1`;
- the hash methods;
- the native tools `vgacap-sample` and `vgacap-export`.

The same code then reads board captures and simulation traces.

**Architecture:**
- **Format v2.** VGCH format v2 adds the following. The board path is untouched (board builds compile `writer.c` alone).
  - samples up to 64 bits;
  - a sample-clock bit and the samples per clock in the header;
  - a `RUNS` chunk with a LEB128 run;
  - `BLKH` block headers;
  - `META` chunks.
- **Container.** Host-only libraries hold the zstd seekable-format container and the compressor thread (`vgacap_trace`), and the samplers (`vgacap_sample`).
- **Vendored code.** zstd, zlib, libfst and SHA-256 are vendored under `third_party/`.
- **Python mirror.** It gets the v2 format, the 12-mode table, and reference implementations used only by tests.

**Tech Stack:** C99 with the existing CMake (warnings as errors), pthreads, vendored zstd 1.5.7 (with `contrib/seekable_format`), zlib 1.3.1, libfst (gtkwave/libfst b2681f9) and a public-domain SHA-256. Python 3.11+ via uv, pytest and numpy (the dev group).

**Spec:** `tinytapeout-vga-videos/docs/superpowers/specs/2026-11-24-raw-frames-and-hash-methods-design.md` (revision 17, commit 8b61aa6), sections "Layer 1" to "Layer 3", "Performance budget" and "Shared code: vgacap".
- Its table "need / in vgacap today / work" is the work list here.
- The pipeline side (`tb.cpp`, `job.py`, `tt-vga`) is a separate plan in that repository. Task 18 is where the two meet.

## Global Constraints

- **Code style.**
  - vgacap code is C99, compiled with `-Wall -Wextra -Werror -Wshadow -Wconversion` (`CMakeLists.txt:8`).
  - SPDX `Apache-2.0` headers on new files.
  - Vendored code is never edited and is built in `third_party/` with its own flags.
- **Board builds stay dependency-free.** `firmware/CMakeLists.txt` and `capture-rp1/Makefile` compile `src/stream/writer.c` on its own, so `writer.c` stays C99 with no `__int128`, no threads and no new includes. Everything host-only (zstd, threads, 128-bit time, mmap) lives in new files under `src/trace/`, `src/sample/` and `src/tools/`.
- **Host extras option.** The host-only libraries are built only when the CMake option `VGACAP_HOST_EXTRAS` is ON (default ON). CI's `c` and `python` jobs build with it ON. A configure with it OFF must still build and pass the existing tests.
- **Bit layout of a simulation sample** (bit 0 least significant):
  - `uo_out` 0-7
  - `uio_out` 8-15
  - `uio_oe` 16-23
  - `ui_in` 24-31
  - `uio_in` 32-39
  - `rst_n` 40
  - `ena` 41
  - `clk` 42

  The trace header has `sample_bits = 43`, `samples_per_clock = 2`, `clock_bit = 42`. Sample `2c` is clk low and `2c + 1` clk high of clock `c`, and clock 0 is the first reset clock.
- **Time rule:** sample `n` is at `round(n * 10^12 / (s * clock_hz))` ps, with halves rounded up, computed in 128-bit integer arithmetic.
- **rgb6:** one byte per pixel, `R << 4 | G << 2 | B`. R = (uo[0], uo[4]), G = (uo[1], uo[5]), B = (uo[2], uo[6]), first bit most significant. Display colour is channel * 85.
- **Performance budget** (spec "Performance budget"), measured in the pipeline's rollout step 2:
  - Recording costs at most 5% of simulation wall time (about 10 ns per clock at the fastest project).
  - Everything after the simulation, plus the compressor thread, costs at most 5% of simulation CPU.
  - Memory is fixed per job.
- **Doubles are formatted** by `vgacap_fmt_double()`: the shortest `%.{p}g`, for p in 1..17, that reads back to the same double. The Python reference uses the same loop. Every `clocks_per_pixel` and every double in a file goes through it.
- **Branches.**
  - Each branch is made in `vgacap/.worktrees/<branch>`, its own worktree.
  - Commits are small, and each is pushed straight away.
  - Each group of tasks becomes one PR to `mithro/vgacap`, reviewed by the tt-vga-capture session before merge.
  - Base: `origin/fw-picosdk` (PR #7, which stacks on #4 and carries `vgacap_writer_attach`). Once #7 is merged, use `origin/main`.
  - Branches stack as the "Branches" table says.
- **Tests:** C tests via `vgacap_add_test` and `ctest`; Python tests in `python/tests/` via `uv run pytest`. Every command's output goes to a log under the worktree's `tmp/` (ignored), and failures are read from the log.

## Branches

| branch | tasks | stacks on |
| --- | --- | --- |
| (tt-vga-capture) `m10-format-note` | 1 | tt-vga-capture `main` |
| `m10-bench` | 2 | base |
| `m10-third-party` | 3 | base |
| `m10-modes` | 4 | base |
| `m10-format-v2` | 5, 6, 7 | base |
| `m10-trace` | 8, 9 | `m10-format-v2` + `m10-third-party` (merge both) |
| `m10-frame-raw` | 10, 11 | `m10-format-v2` |
| `m10-samplers` | 12, 13, 14, 15 | `m10-trace` + `m10-frame-raw` + `m10-modes` |
| `m10-sample-tool` | 16 | `m10-samplers` |
| `m10-export` | 17 | `m10-trace` |
| `m10-tbv1-vectors` | 18 | `m10-sample-tool`, after the pipeline plan's `tb.cpp` test exists |

Gate: Tasks 5 onward follow the format as the owner approves it in Task 1. If the owner changes the chunk layout, Tasks 5-9 change to match before they start.

## Review Focus

1. **A trace cut off by a kill** (the last block half-written, no seek table). The reader returns every complete block and reports `truncated`; it does not fail. Test: Task 9 `test_trace_truncated`.
2. **A design whose pins do not change for longer than 2^32 samples** (a static picture after reset). Blocks still close every 2^24 clocks, run lengths are exact and the sample count is exact. Tests: Task 8 `test_trace_long_static_run` and Task 7 `split_run_equals_unsplit`.
3. **The clock rule broken in the encoder** (a harness that forgets a half clock). The writer fails at once, naming the sample, instead of writing a trace whose clock is wrong. Test: Task 8 `test_trace_clock_rule_violation`.
4. **A trace that ends during calibration** (SIGTERM early, or `calib_seconds` longer than the run). Calibration reports what it saw, both samplers emit no frames, and `vgacap-sample` still writes valid `frames.txt` files with `frames: 0`. Test: Task 16 `test_sample_ends_in_calibration`.
5. **A vsync glitch inside the pulse.** The frame clock counts an extra end; `tb-v1` numbers it as `tb.cpp` would, and `centre-v1` leaves the earlier number as a gap (`-`). The two samplers' later frames keep the same numbers. Test: Task 13 `test_centre_glitch_gap`.

---

## File structure

Created in vgacap (paths relative to the repository root):

| file | responsibility |
| --- | --- |
| `include/vgacap/stream.h` (modify) | v2 header fields, `RUNS`/`BLKH`/`META` tags, the 64-bit run event, the LEB128 and pair helpers |
| `src/stream/writer.c`, `src/stream/reader.c` (modify) | v2 header, `RUNS`, `BLKH`, `META` |
| `include/vgacap/time.h`, `src/stream/time.c` | sample time in ps (128-bit), `vgacap_fmt_double` |
| `include/vgacap/frame.h`, `src/frame/*.c` (modify) | 12-mode table with the `extended` mark; `vgaframe_push64`; raw-frame callback; boundary clearing; rgb6 output; the learner's last report |
| `include/vgacap/trace.h`, `src/trace/trace_write.c`, `src/trace/trace_read.c` | the seekable container, writer with inline push and compressor thread, reader with range reads and seek-table rebuild |
| `include/vgacap/sample.h`, `src/sample/calib.c`, `src/sample/frameclock.c`, `src/sample/tbv1.c`, `src/sample/centrev1.c`, `src/sample/hashes.c` | shared calibration, frame clock, the two samplers, hash methods |
| `src/tools/vgacap_sample.c`, `src/tools/vgacap_export.c` | the two native tools |
| `third_party/CMakeLists.txt`, `third_party/{zstd,zlib,libfst,sha256}/`, `third_party/README.md` | vendored code with licences |
| `bench/bench_runs.c` | Task 2 benchmark |
| `python/vgacap/stream.py`, `python/vgacap/modes.py` (modify) | v2 mirror, 12 modes |
| `python/vgacap/timebase.py`, `python/vgacap/calib.py`, `python/vgacap/tbv1.py`, `python/vgacap/centre.py`, `python/vgacap/hashes.py`, `python/vgacap/framesfile.py`, `python/vgacap/synthtrace.py` | test references and file formats |
| `docs/trace-format.md` | the trace format, sample-to-time rule and bit layout, precise enough to read without our code |

In tt-vga-capture: `docs/design/2026-11-25-format-v2-runs.md` (Task 1), `docs/research/2026-11-25-libvgaframe-runs-benchmark.md` (Task 2), and `TASKS.md` Milestone 10.

---

### Task 1: format design note (owner decision 1)

**Files:**
- Create: tt-vga-capture `docs/design/2026-11-25-format-v2-runs.md`.
- Modify: tt-vga-capture `TASKS.md` (Milestone 10 ticks).

**Interfaces:**
- Produces: the byte layouts Tasks 5-9 implement, as approved.

- [ ] **Step 1: Write the note.** It proposes exactly the layouts below. It answers the pending compact-RLE question from `docs/research/2026-11-24-board-rle-throughput.md`: the board's u8 value plus a LEB128 run is a `RUNS` chunk with `sample_bits = 8`, so the same chunk serves both uses.

  It also states two alternatives with their costs:
  - the planar alternative (`uo_out` per sample, plus a 64-bit-valued `EVNT`), needed only if rollout step 2 shows the busiest designs over budget;
  - keeping `RLE ` and adding only 64-bit runs.

  The layouts, all little-endian:
  - **VGCH version 2:**
    - Bytes 0-19 are the same as version 1, except:
      - `sample_bits` may be 1..64;
      - `samples_per_word` is 0 when `sample_bits > 32` (`RAW `, `FRAM`, `RLE ` and `EVNT` are then not allowed).
    - Then four new bytes:
      - byte 20 `samples_per_clock` (1 or 2; 1 for board captures);
      - byte 21 `clock_bit` (0..63, or 0xFF for none);
      - byte 22 `clock_first` (0 or 1, the clock bit's value in sample 0);
      - byte 23 reserved, which must be 0.
    - Then `desc_len` bytes of description. The chunk length is `24 + desc_len`.
    - A stream with a `clock_bit` may contain only `RUNS`, `BLKH`, `META` and `TIME` chunks.
  - **`RUNS`:**
    - `u32 pair_count`, then `pair_count` pairs. Each pair is:
      - `value`, `vbytes = ceil(sample_bits / 8)` bytes, little-endian, with the clock bit stored as 0;
      - `run`, LEB128 u64, at least 1, minimal encoding (no trailing `0x80 0x00`), at most 10 bytes.
    - The chunk length must equal `4 +` the pairs' bytes exactly.
    - The reader sets the clock bit of each run's value to `clock_first ^ (n & 1)`, where `n` is the run's first sample.
  - **`BLKH`:** `u64 first_sample`, the sample number of the block's first sample.
  - **`META`:**
    - 1..4096 bytes of UTF-8 text: `key=value` lines, each ending `\n`.
    - The first line is `meta=open` or `meta=close`.
    - Keys in the opening chunk: `project`, `override`, `clock_hz`, `calib_seconds`, `seconds`, `simulator`, `harness`, `layout=tt-um-43`.
    - Keys in the closing chunk: `capture_after_clock`, `status`, `frames`.
  - **Container:**
    - A trace file is zstd's seekable format. Each zstd frame is one block. The seek table is a skippable frame at the end.
    - Block 0 is `VGCH`, `META(open)`, `BLKH(0)`, then `RUNS`. Every later block is `BLKH(first)`, then `RUNS`.
    - The last block ends with `META(close)`.
    - A block closes before its uncompressed size would pass 16 MiB minus 64 KiB, or at 2^24 clocks (`2^24 * samples_per_clock` samples). A run that would cross the boundary is split.
- [ ] **Step 2: Have it reviewed.** Commit and push it on tt-vga-capture branch `m10-format-note`. Ask the "Tiny Tapeout board direct VGA capture" session to review it. Put it to Tim for decision 1. Record the decision and its date at the top of the note.
- [ ] **Step 3: Tick the TASKS.md item.** Tick "Design note: 64-bit samples plus an RLE64 chunk" in TASKS.md, citing the note.

### Task 2: libvgaframe benchmark on run input

**Files:**
- Create: `bench/bench_runs.c`; add an `add_executable(bench-runs ...)` line in `CMakeLists.txt` under the frame section, not as a test.
- Create: tt-vga-capture `docs/research/2026-11-25-libvgaframe-runs-benchmark.md`.

**Interfaces:**
- Consumes: `vgaframe_init`, `vgaframe_push`, `vgaframe_timing_push`, as on the base branch.

- [ ] **Step 1: Write `bench-runs`.** Usage: `bench-runs --clocks N --profile busy|bars|static`. It builds one 640x480@60 frame (800 x 525 clocks, Tiny VGA samples, the synth layout of `tests/synth.c`) as runs:
  - `busy`: a new colour every clock in the active area;
  - `bars`: 64 bars of 10 clocks;
  - `static`: one colour.

  It replays the frame's runs until N clocks have been pushed, through `vgaframe_push` with the buffer sizes the spec fixes (`max_clocks_per_line = 7596`, `max_lines = 1200`). It times the replay with `clock_gettime(CLOCK_MONOTONIC)` and prints one line: `profile=<p> clocks=<N> runs=<R> seconds=<s> ns_per_clock=<x> ns_per_run=<y> frames=<F>`.
- [ ] **Step 2: Run it.** Run `build/bench-runs --clocks 1500000000 --profile P` for each profile on big-storage, logging to `tmp/bench.log`. `frames` must be `1500000000 / 420000`, rounded down, minus at most 2 (the first frame and the cut-off last one).
- [ ] **Step 3: Write the research note.** It records:
  - the three lines;
  - the host CPU;
  - the comparison with the spec's budget: 5% of the fastest simulation's 220 ns/clock is 11 ns/clock for all post-simulation work;
  - what that leaves for the samplers.

  If `busy` is over 11 ns/clock, the note says by how much, and what in `vgaframe_push` costs it (from `perf record` on the same run).
- [ ] **Step 4: Commit, push and tick.** Commit and push the benchmark on `m10-bench` and the note in tt-vga-capture. Tick the TASKS.md item.

### Task 3: vendored zstd, zlib, libfst and SHA-256

**Files:**
- Create: `third_party/CMakeLists.txt`, `third_party/README.md` (source URL, version or commit, licence, and the files taken, for each package).
- Create (vendored):
  - `third_party/zstd/` (zstd v1.5.7: `lib/` and `contrib/seekable_format/{zstd_seekable.h,zstdseek_compress.c,zstdseek_decompress.c}`, `LICENSE`);
  - `third_party/zlib/` (zlib v1.3.1 sources and `LICENSE`);
  - `third_party/libfst/` (gtkwave/libfst at b2681f927a092a21b42ba1f3b2a9af831deaf58d: `src/fstapi.{c,h}`, `fastlz.{c,h}`, `lz4.{c,h}`, `LICENSE`, MIT);
  - `third_party/sha256/` (Brad Conte's public-domain `sha256.{c,h}` from crypto-algorithms, with its public-domain statement).
- Modify: `CMakeLists.txt` (`option(VGACAP_HOST_EXTRAS ... ON)`, `add_subdirectory(third_party)` under it).
- Test: `tests/test_third_party.c`.

Note for the spec's owner: libfst needs zlib (`compress2`, `uncompress` and the `gz*` calls in `fstapi.c`), which the spec's vendoring list leaves out. It does not use bzip2. zlib is vendored here so that "no new system package" still holds.

**Interfaces:**
- Produces: static libraries `vgacap_zstd` (with seekable), `vgacap_zlib`, `vgacap_fst` (links `vgacap_zlib` and `Threads::Threads`) and `vgacap_sha256`. Each exports its include directory with `target_include_directories(... SYSTEM PUBLIC ...)`, so vgacap's warnings never apply to vendored headers.

- [ ] **Step 1: Write the failing test.** Write `tests/test_third_party.c` with:
  - `zstd_round_trip`: 1 MiB of pattern data, compressed at level 3 and decompressed, gives equal bytes.
  - `seekable_two_frames`: two blocks are compressed as separate frames with `ZSTD_seekable_logFrame` and a seek table written by `ZSTD_seekable_writeSeekTable`. Reading back gives `ZSTD_seekable_getNumFrames == 2`, and `ZSTD_seekable_decompressFrame(…, 1)` returns block 1's bytes.
  - `sha256_abc`: SHA-256 of `"abc"` is `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`.
  - `fst_write_read`: write a 1-bit and an 8-bit signal with three changes to an FST file in the test's working directory (no `/tmp`), read it back with `fstReaderIterBlocks2`, and get the same three (time, handle, value) changes.
- [ ] **Step 2: Run the test and watch it fail.** Run `cmake -S . -B build && cmake --build build -j > tmp/build.log 2>&1`. Expected: the build fails, because `third_party` is missing.
- [ ] **Step 3: Vendor and build.** Vendor the four packages at the versions above. Write `third_party/CMakeLists.txt` that:
  - starts with `set_directory_properties(PROPERTIES COMPILE_OPTIONS "")`, so vgacap's `-Werror -Wconversion` do not reach vendored code;
  - sets `-O2 -w`;
  - defines `HAVE_LIBPTHREAD`, `FST_WRITER_PARALLEL`, `HAVE_FSEEKO` and `HAVE_REALPATH` for libfst (no `config.h`);
  - builds zstd's `lib/common`, `lib/compress` and `lib/decompress` plus the seekable files, with `ZSTD_MULTITHREAD` off and `ZSTD_LEGACY_SUPPORT=0`.
- [ ] **Step 4: Run all tests.** Run `ctest --test-dir build --output-on-failure > tmp/ctest.log 2>&1`. Expected: all tests pass, including `test_third_party`. Then configure with `-DVGACAP_HOST_EXTRAS=OFF` into `build-off/`: everything except `test_third_party` builds and passes.
- [ ] **Step 5: Commit.** Commit in three steps: one commit per vendored package (`third_party: vendor zstd 1.5.7` and so on), then the CMake and test commit. Push.

### Task 4: the shared 12-mode table

**Files:**
- Modify: `include/vgacap/frame.h` (struct field, comments at `frame.h:27-31`), `src/frame/modes.c`, `src/frame/frame.c:42-47` (comment).
- Modify: `python/vgacap/modes.py`.
- Modify: `python/ttcap/capture.py` (`frame_cfg`).
- Test: `tests/test_modes.c`, `tests/test_frame.c`, `python/tests/test_modes_table.py`, `python/tests/test_ttcap_capture.py`.

**Interfaces:**
- Produces:
  - `vgaframe_mode_t` gains `uint8_t extended;`: 1 for the five modes added from `tb.cpp`, which `vgaframe_mode_match_cpl` skips.
  - The table order is the existing seven, unchanged, then `800x600@72`, `800x600@75`, `1024x768@70`, `1280x720@60`, `1280x1024@60`.
  - Python `Mode` gains `extended: bool = False`, plus `vgacap.modes.TABLE` (the ordered list), `match(cpl, lpf)` and `match_cpl(cpl)`, which mirror the C.

The five rows (clock fields at one clock per pixel; polarities from VESA DMT, and CEA-861 for 1280x720):

| name | h_active, front, sync, back | v_active, front, sync, back | h+, v+ |
| --- | --- | --- | --- |
| 800x600@72 | 800, 56, 120, 64 | 600, 37, 6, 23 | 1, 1 |
| 800x600@75 | 800, 16, 80, 160 | 600, 1, 3, 21 | 1, 1 |
| 1024x768@70 | 1024, 24, 136, 144 | 768, 3, 6, 29 | 0, 0 |
| 1280x720@60 | 1280, 110, 40, 220 | 720, 5, 5, 20 | 1, 1 |
| 1280x1024@60 | 1280, 48, 112, 248 | 1024, 1, 3, 38 | 1, 1 |

- [ ] **Step 1: Write the failing tests.** In `test_modes.c`:
  - `table_has_12`: `n == 12`, and entries 0-6 are unchanged by name, in order.
  - `added_totals_match_tb_cpp`: for each added mode, `cpl` and `lpf` equal `tb.cpp:45-50`'s `line_px` and `lines` (1040x666, 1056x625, 1328x806, 1650x750, 1688x1066), and sync widths and back porches equal its `hpulse`, `hback`, `vpulse` and `vback`.
  - `pairs_distinct`: the 12 `(cpl, lpf)` pairs are distinct.
  - `match_cpl_unchanged`: for every non-extended entry, `vgaframe_mode_match_cpl(cpl)` returns that entry, and `vgaframe_mode_match_cpl(1056)` returns `800x600@60`, not `@75`.
  - `match_sees_added`: `vgaframe_mode_match(1040, 666)` returns `800x600@72`.

  In `test_frame.c`, `crop_added_modes`: a `synth_frame` stream of three frames in each added mode emits frames of exactly that mode's `h_active x v_active`, with every pixel equal to the synth pattern.

  `test_modes_table.py`: run `build/test_modes --dump` (a new flag that prints every C entry as `name,h_active,h_front,h_sync,h_back,v_active,v_front,v_sync,v_back,hpos,vpos,extended`), and check that each line equals the Python `TABLE`, field by field.

  `test_ttcap_capture.py::test_frame_cfg_rejects_extended`: `frame_cfg(profile, vga_mode="800x600@72")` raises `ValueError` whose message contains `"not unique by clocks per line"`.
- [ ] **Step 2: Run the tests and watch them fail.** Run `ctest` and `uv run pytest python/tests/test_modes_table.py python/tests/test_ttcap_capture.py`. Expected: failures on the new tests only.
- [ ] **Step 3: Implement.**
  - Add the field and rows, setting `extended = 0` explicitly on the existing seven.
  - `vgaframe_mode_match_cpl` skips `extended` entries.
  - Update the "unique across the built-in table" comments (`frame.c:46-47`, `frame.h:27-28`) to say uniqueness holds for the non-extended entries, which is all the function looks at.
  - Mirror the change in Python.
  - In `frame_cfg`, after the unknown-mode check: `if mode.extended: raise ValueError(f"{vga_mode}: not unique by clocks per line, so a frame or window capture cannot recognise it; streaming capture detects it without --vga-mode")`.
- [ ] **Step 4: Run the tests and see them pass.** Run the same commands. Expected: everything passes, including every pre-existing test.
- [ ] **Step 5: Commit and push** on `m10-modes`.

### Task 5: format v2 in the C stream library and the Python mirror

**Files:**
- Modify: `include/vgacap/stream.h`, `src/stream/writer.c`, `src/stream/reader.c`, `src/tools/vgacap_dump.c`, `src/tools/vgacap_frames.c`, `gst/gstvgadecode.c`.
- Modify: `python/vgacap/stream.py`.
- Test: `tests/test_stream_v2.c` (new), `tests/test_stream_chunks.c`, `python/tests/test_stream_v2.py` (new), `python/tests/test_roundtrip_c.py`.

**Interfaces:**
- Produces (C, `stream.h`):
  - **Tags:** `#define VGACAP_TAG_RUNS "RUNS"`, `VGACAP_TAG_BLOCK "BLKH"`, `VGACAP_TAG_META "META"`, `#define VGACAP_META_MAX 4096`, `#define VGACAP_CLOCK_BIT_NONE 0xFF`.
  - **`vgacap_header_t` gains** `uint8_t samples_per_clock, clock_bit, clock_first;`. `version` is 1 or 2.
  - **`vgacap_header_init_tinyvga` sets** `samples_per_clock = 1` and `clock_bit = VGACAP_CLOCK_BIT_NONE`. It still makes a version 1 header.
  - **New function:** `void vgacap_header_init_v2(vgacap_header_t *h, uint8_t sample_bits, uint8_t samples_per_clock, uint8_t clock_bit, uint8_t clock_first)`. It sets version 2, `samples_per_word = 0` when `sample_bits > 32`, else 1, and the Tiny VGA map on bits 0-7.
  - **`size_t vgacap_leb128_put(uint8_t *p, uint64_t v)`:** returns 1..10.
  - **`size_t vgacap_run_pair_put(uint8_t *p, uint64_t value, unsigned vbytes, uint64_t run)`:** returns the bytes written. `vbytes = (sample_bits + 7) / 8`.
  - **New writers:** `int vgacap_writer_runs(vgacap_writer_t *w, const uint64_t *values, const uint64_t *runs, uint32_t pair_count)`, `int vgacap_writer_block(vgacap_writer_t *w, uint64_t first_sample)`, `int vgacap_writer_meta(vgacap_writer_t *w, const char *text, size_t len)`.
  - **`vgacap_writer_init`** writes the 24-byte fixed part when `h->version == 2`.
  - **`vgacap_writer_attach`** works unchanged for both versions.
  - **Event changes:**
    - `VGACAP_EV_RUN`'s `u.run` becomes `{ uint64_t value; uint64_t run; }`;
    - new `VGACAP_EV_BLOCK` (`u.block { uint64_t first_sample; uint64_t expected; }`, where `expected` is the reader's running sample position before the chunk);
    - new `VGACAP_EV_META` (`u.meta { const char *text; uint16_t len; }`, valid during the callback).
  - **`vgacap_reader_t` gains** `uint64_t sample_pos` (samples delivered so far, set to `first_sample` by every `BLKH`) and a `char metabuf[VGACAP_META_MAX + 1]`.
  - **New function:** `void vgacap_reader_init_header(vgacap_reader_t *r, vgacap_event_fn cb, void *user, const vgacap_header_t *h)`. It starts a reader that already knows the header, for decoding a block other than block 0. It emits no `HEADER` event.
- Produces (Python `vgacap.stream`):
  - `Header` gains `samples_per_clock=1`, `clock_bit=0xFF` and `clock_first=0`.
  - `Writer.runs(pairs)`, `Writer.block(first_sample)` and `Writer.meta(text)`.
  - `read_stream` yields `("run", value, run)` with the clock bit filled in, `("block", first_sample)` and `("meta", text)`.
  - `leb128_encode(v) -> bytes` and `leb128_decode(buf, pos) -> (v, pos)`.

- [ ] **Step 1: Write the failing C tests.** `tests/test_stream_v2.c` contains:
  - `leb128_vectors`: 1 → `01`, 127 → `7f`, 128 → `80 01`, 300 → `ac 02`, 2^32 → `80 80 80 80 10`, 2^64−1 → `ff ff ff ff ff ff ff ff ff 01`.
  - `header_v2_round_trip`: a v2 header (43 bits, 2 per clock, clock bit 42, `clock_first` 0, desc `"t"`) written then read gives the same fields, and the VGCH payload length is 25.
  - `runs_round_trip_43bit`: write pairs `(0x1_0000_0001, 1)`, `(0x0FF, 2^32 + 5)`, `(0x3FF_FFFF_FFFF & ~(1ull<<42), 3)`. Reading back gives the same runs, with each value's bit 42 equal to `n & 1` for the run's first sample `n` (0, 1, 2^32 + 6).
  - `runs_reject_clock_bit_set`: a stored value with bit 42 set resyncs, `what == "RUNS value has the clock bit set"`.
  - `runs_reject_overlong_leb`: run bytes `81 80 00` (non-minimal) resync, `what == "RUNS run not minimally encoded"`.
  - `runs_reject_zero_run` (`what == "RUNS run is zero"`) and `runs_length_mismatch` (`what == "RUNS pairs do not fill the chunk"`).
  - `clock_stream_rejects_raw`: a `RAW ` chunk in a stream with a clock bit resyncs, `what == "chunk not allowed with a sample clock"`.
  - `block_sets_position`: `BLKH(1000)` after 10 samples gives `EV_BLOCK{first_sample = 1000, expected = 10}`, and the next run's clock bit follows sample 1000.
  - `meta_event`: `META("meta=open\nproject=x\n")` arrives intact. Lengths 0 and 4097 resync.
  - `init_header_decodes_block`: a reader made with `vgacap_reader_init_header` decodes a `BLKH` + `RUNS` byte string with no VGCH.
  - `v1_streams_unchanged`: every `test_stream_chunks.c` byte vector still decodes the same.
- [ ] **Step 2: Write the failing Python tests.** `python/tests/test_stream_v2.py`: the same LEB128 vectors; a Python-written v2 stream read by `read_stream`; and, through the existing `vgacap-dump` C cross-check pattern, a v2 stream with `RUNS` dumps `total_samples` equal to the Python sum of runs, and prints `VGCH v2 bits=43 spc=2 clock_bit=42`.
- [ ] **Step 3: Run the tests and watch them fail.** Run `ctest` and `uv run pytest python/tests/test_stream_v2.py`. Expected: build or assertion failures in the new tests only.
- [ ] **Step 4: Implement.**
  - **Reader.** The fixed-header parse becomes version-dependent: 20 bytes for v1, 24 for v2, and `pbuf` grows to 24 bytes. The v2 checks are:
    - `sample_bits` in 1..64;
    - `samples_per_word == 0` iff `sample_bits > 32`;
    - `samples_per_clock` in {1, 2};
    - `clock_bit < sample_bits` or 0xFF;
    - `clock_first` ≤ 1;
    - the reserved byte is 0.
  - **Pair parse.** `RUNS` pairs are parsed incrementally, byte by byte, like the other chunks, with a small state machine (value bytes, then LEB bytes). Do not buffer the whole chunk.
  - **Old chunks.** `RAW `, `RLE `, `FRAM` and `EVNT` widen their run event fields to 64 bits and keep their semantics. They resync in v2 streams with `sample_bits > 32` or with a clock bit.
  - **Callers:**
    - `vgacap_dump.c` prints v2 fields and counts runs in 64 bits.
    - `vgacap_frames.c` and `gst/gstvgadecode.c` call `vgaframe_push64(&f, (uint32_t)ev->u.run.value, ev->u.run.run)`.
    - Until Task 7 lands on the same branch, they keep `vgaframe_push` with an explicit `(uint32_t)` run cast. Task 7 replaces it.
  - **Python.** Mirror all of this in `stream.py`.
- [ ] **Step 5: Run the tests and see them pass.** Run `ctest` and the full `uv run pytest`. Expected: everything passes.
- [ ] **Step 6: Commit and push.** Commit in small steps (header, `RUNS`, `BLKH`/`META`, callers, Python), pushing each, on `m10-format-v2`.

### Task 6: the time rule and double formatting

**Files:**
- Create: `include/vgacap/time.h`, `src/stream/time.c` (added to `vgacap_stream` only when the compiler has `__int128`; checked in CMake with `check_c_source_compiles`).
- Create: `python/vgacap/timebase.py`.
- Test: `tests/test_time.c`, `python/tests/test_timebase.py`.

**Interfaces:**
- Produces:
  - `uint64_t vgacap_sample_time_ps(uint64_t n, uint32_t samples_per_clock, uint32_t clock_hz)`: halves round up; `clock_hz == 0` returns 0.
  - `int vgacap_fmt_double(char *buf, size_t len, double v)`: the shortest round-tripping `%.{p}g`.
  - Python `sample_time_ps(n, s, hz)` and `fmt_double(v)`.

- [ ] **Step 1: Write the failing tests.** `time_vectors` checks, for (n, s, hz):
  - (1, 2, 25175000) → 19861
  - (2, 2, 25175000) → 39722
  - (3, 2, 25175000) → 59583
  - (12000000000, 2, 25175000) → 238331678252234
  - (12000000001, 2, 25175000) → 238331678272095
  - (1, 1, 25175000) → 39722
  - (3, 2, 48000000) → 31250
  - (0, 2, 25175000) → 0

  `no_drift`: for n in 0..10^6, `t(n+1) - t(n)` is 19860 or 19861 at 25.175 MHz, s = 2.

  `fmt_double_vectors`: 1.0 → `"1"`, 1.90625 → `"1.90625"`, 832.0/800 → `"1.04"`, 800.0/840 → `"0.95238095238095233"`, 25175000.0 → `"25175000"`.

  The Python tests use the same vectors, plus 10^4 random `n` below 1.3e10 checked against `Fraction` arithmetic.
- [ ] **Step 2: Run the tests and watch them fail.** Expected: undefined references.
- [ ] **Step 3: Implement.** Use `unsigned __int128`: `(2 * n * 10^12 + d) / (2 * d)` with `d = s * clock_hz`.
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Commit and push** on `m10-format-v2`.

### Task 7: 64-bit runs into libvgaframe, and the learner's report

**Files:**
- Modify: `include/vgacap/frame.h`, `src/frame/frame.c`, `src/frame/timing.c` (the comment at `timing.c:13-14`).
- Test: `tests/test_frame.c`, `tests/test_timing.c`.

**Interfaces:**
- Produces:
  - `void vgaframe_push64(vgaframe_t *f, uint32_t sample, uint64_t run)` and `int vgaframe_timing_push64(vgaframe_timing_learner_t *l, uint8_t hsync, uint8_t vsync, uint64_t run)`. Each splits `run` into pieces of at most `UINT32_MAX`; the second returns the first piece's report, since reports happen only at a run's first clock.
  - `vgaframe_t` gains `int last_report`: the learner's return value for the most recent `vgaframe_push`, which samplers read to date line and frame starts.

- [ ] **Step 1: Write the failing tests.**
  - `split_run_equals_unsplit` (test_timing.c): a learner fed three frames, then one constant run of `2^32 + 1000` clocks, then three more frames, ends in the same state (`memcmp` of `vgaframe_timing_t` and the counters `clk_in_line`, `line_in_frame`, `h_high`, `h_low`) as one fed the long run as `2^32 - 1`, then `1001` (by hand), and as `vgaframe_timing_push64`.
  - `last_report_values` (test_frame.c): across a synth 640x480@60 stream fed one clock at a time, `last_report` is 1 on each line start's push, 2 on each frame start's push, and 0 otherwise.
- [ ] **Step 2: Run the tests and watch them fail.**
- [ ] **Step 3: Implement.** In `vgaframe_push`, store the learner's return in `f->last_report`. Fix the `timing.c:13-14` comment to say the call is made at the hsync *trailing* edge, when a line is accepted. Switch `vgacap_frames.c` and `gstvgadecode.c` to `vgaframe_push64`.
- [ ] **Step 4: Run the tests and see them pass.** Run all of `ctest` and `pytest`.
- [ ] **Step 5: Commit and push** on `m10-format-v2`.

### Task 8: the trace writer (container, inline push, compressor thread)

**Files:**
- Create: `include/vgacap/trace.h`, `src/trace/trace_write.c`, `src/trace/blocks.c` (block assembly shared with tests).
- Modify: `CMakeLists.txt`: library `vgacap_trace` (links `vgacap_stream`, `vgacap_zstd`, `Threads::Threads`) under `VGACAP_HOST_EXTRAS`.
- Test: `tests/test_trace_write.c`.

**Interfaces:**
- Produces (`trace.h`):

```c
#define VGACAP_TRACE_BLOCK_BYTES   (16u * 1024u * 1024u)
#define VGACAP_TRACE_BLOCK_RESERVE (64u * 1024u)    // closing META and the last pair
#define VGACAP_TRACE_BLOCK_CLOCKS  (1ull << 24)

// Fields above `impl` are read by the inline push; do not touch them.
typedef struct vgacap_trace_writer {
    uint64_t cur;        // the current run's value, clock bit cleared
    uint64_t run;        // samples in the current run
    uint64_t n;          // number of the next sample
    uint64_t limit;      // n at which the slow path must run (block end); 0 before the first sample
    uint64_t clk_mask;   // 1 << clock_bit, or 0
    uint64_t clk_expect; // clk_mask if the clock bit must be 1 at sample n, else 0
    struct vgacap_trace_impl *impl;
} vgacap_trace_writer_t;

vgacap_trace_writer_t *vgacap_trace_create(const char *path, const vgacap_header_t *h,
                                           const char *open_meta, int zstd_level,
                                           char *err, size_t errlen);
int vgacap_trace_slow(vgacap_trace_writer_t *t, uint64_t v);       // not for callers
static inline int vgacap_trace_push(vgacap_trace_writer_t *t, uint64_t v) {
    if (((v ^ t->clk_expect) & t->clk_mask) | ((v & ~t->clk_mask) ^ t->cur) | (uint64_t)(t->n == t->limit))
        return vgacap_trace_slow(t, v);
    t->run++; t->n++; t->clk_expect ^= t->clk_mask; return 0;
}
// Ends the last run, writes META(close) in the last block, the seek table,
// joins the thread, frees `t`. Returns 0, or -1 with `err` set.
int vgacap_trace_finish(vgacap_trace_writer_t *t, const char *close_meta, char *err, size_t errlen);
// Frees `t` without a closing chunk or seek table (what a kill leaves, for tests).
void vgacap_trace_abandon(vgacap_trace_writer_t *t);
```

  - The slow path ends the current run when the value changes, and closes a block when `n` reaches `limit`.
  - Runs are encoded with `vgacap_run_pair_put` straight into the block buffer, inside one `RUNS` chunk per block whose length and count are patched when the block closes.
  - A finished block is handed to the compressor thread. That thread runs `ZSTD_compress2` at `zstd_level` with checksums, writes the block through a 1 MiB `setvbuf`'d `FILE*`, and logs it with `ZSTD_seekable_logFrame`.
  - There are two block buffers. If the thread still holds the other one, the slow path waits on a condition variable; nothing is dropped.
  - A broken clock rule, or any I/O error, makes every later push and `finish` return -1. The message names the sample: `"sample 12345: clock bit is 0, expected 1"`.

- [ ] **Step 1: Write the failing tests.** Every test writes into `tmp/` under the build directory, and reads back with the reference reader in the test: whole-file `ZSTD_decompress` of every frame, fed to `vgacap_reader_feed`.
  - `test_trace_small`: 43-bit header; 1,000 clocks of a pattern that changes `uo_out` every 7 clocks, `clk` correct. Reading back gives the same 2,000 samples, `META(open)` first, `META(close)` last, and one block.
  - `test_trace_blocks_by_clock`: a static value for `3 * 2^24 + 5` clocks gives 4 blocks with `BLKH` first samples 0, 2^25, 2^26 and 3 * 2^25. Each block holds exactly one pair, except the last.
  - `test_trace_blocks_by_bytes`: alternating values every sample, for enough samples to need more than 16 MiB, closes a block before `VGACAP_TRACE_BLOCK_BYTES`. Every block's uncompressed size is `≤ VGACAP_TRACE_BLOCK_BYTES`, and every chunk is `≤ VGACAP_MAX_CHUNK_LEN`.
  - `test_trace_long_static_run`: a v2 header with `sample_bits = 1`, one sample per clock and no clock bit. The constant value 1 is pushed `2^32 + 10` times (a few seconds). Total samples read is `2^32 + 10`; blocks close every `2^24` samples; no run crosses a `BLKH`; and each block's single pair has run `2^24`, except the last's, which is 10.
  - `test_trace_clock_rule_violation`: push sample 0 with clk 0, then sample 1 with clk 0. The push returns -1, and `finish` returns -1 with `err == "sample 1: clock bit is 0, expected 1"`.
  - `test_trace_seek_table`: `ZSTD_seekable_initFile` on the result reports one frame per block, with decompressed sizes summing to the stream length.
  - `test_trace_push_speed`: 2e8 pushes of a value that changes every 400 samples, timed. Print ns per push, and fail only above 10 ns per sample on this host. The spec's budget is about 10 ns per clock at two samples, so this checks the whole push side with headroom for the harness. It is labelled `perf` in CTest, so `ctest -LE perf` can skip it on slow CI runners.
- [ ] **Step 2: Run the tests and watch them fail.**
- [ ] **Step 3: Implement** as the Interfaces block describes. Block 0's VGCH and `META(open)` are written by `vgacap_writer_init` and `vgacap_writer_meta` through a write callback that appends to the block buffer.
- [ ] **Step 4: Run the tests and see them pass.** Run `ctest --test-dir build --output-on-failure > tmp/ctest.log 2>&1` and read the log.
- [ ] **Step 5: Commit and push** on `m10-trace`.

### Task 9: the trace reader (ranges, rebuild, plain VGCH)

**Files:**
- Create: `src/trace/trace_read.c`; extend `include/vgacap/trace.h`.
- Modify: `src/tools/vgacap_dump.c` (reads traces through it: `vgacap-dump` on a `.trace.zst` prints its chunks).
- Test: `tests/test_trace_read.c`.

**Interfaces:**
- Produces:

```c
typedef struct vgacap_trace_info {
    vgacap_header_t header;
    const char *open_meta;    // text of META(open) or NULL
    const char *close_meta;   // NULL when the trace was cut short
    uint64_t samples;         // samples in the complete blocks
    uint32_t blocks;
    uint8_t  compressed;      // 0 for a plain VGCH file
    uint8_t  table_rebuilt;   // 1 if the seek table was missing or bad
} vgacap_trace_info_t;

typedef struct vgacap_trace_reader vgacap_trace_reader_t;
// value: the run's 64-bit value with the clock bit of its first sample;
// return nonzero to stop.
typedef int (*vgacap_trace_run_fn)(void *user, uint64_t first_sample, uint64_t value, uint64_t run);
vgacap_trace_reader_t *vgacap_trace_open(const char *path, char *err, size_t errlen);
const vgacap_trace_info_t *vgacap_trace_info(const vgacap_trace_reader_t *r);
// Delivers every run overlapping [from, to), clipped to it, in order.
int vgacap_trace_read(vgacap_trace_reader_t *r, uint64_t from, uint64_t to,
                      vgacap_trace_run_fn fn, void *user, char *err, size_t errlen);
void vgacap_trace_close(vgacap_trace_reader_t *r);
```

  - **Opening:**
    - The file is `mmap`ed read-only.
    - The zstd magic `28 b5 2f fd` means compressed; `VGCH` means plain, which is one pseudo-block, read from the start for any range.
    - The seek table is read with `ZSTD_seekable_initBuff`.
    - If that fails, the reader walks the frames with `ZSTD_findFrameCompressedSize`, stopping at the first frame that is incomplete or fails its checksum, and decompresses only enough of each block for its `BLKH`.
    - `close_meta` comes from decompressing the last complete block.
  - **Ranges.** `--from/--to` map to blocks by binary search on the blocks' first samples, and each block is decoded with `vgacap_reader_init_header`.

- [ ] **Step 1: Write the failing tests.** They use traces made with Task 8's writer:
  - `test_trace_range`: on the 3-block static trace, `read(2^25 - 3, 2^25 + 4)` delivers runs totalling 7 samples, with first samples `2^25 - 3` and `2^25`.
  - `test_trace_clock_bits`: on a small trace, `value >> 42 & 1 == (first_sample & 1)` for every delivered run when `clock_first == 0`.
  - `test_trace_truncated`: copy a 5-block trace, cutting it 100 bytes into block 4's zstd frame (no seek table). `open` succeeds with `table_rebuilt = 1`, `blocks = 4`, `close_meta = NULL`, and `samples` equal to the first 4 blocks' samples. A full read delivers exactly those samples.
  - `test_trace_truncated_in_table`: cut the file inside the seek table. The result is the same as above, with all 5 blocks, and with `close_meta` present, since the last block is whole.
  - `test_trace_plain_vgch`: a plain v2 VGCH file written by the Python writer reads the same as its compressed copy.
  - `test_trace_v1_capture`: `tests/fixtures/tiny-logo-capture.vgacap.gz`, gunzipped into `tmp/` by the test, opens with `compressed = 0`, `header.version = 1`, and the same sample total as `vgacap-dump` prints.
  - In `python/tests/test_roundtrip_c.py`, a new case runs `vgacap-dump` on a Task 8 trace and checks its `total_samples`.
- [ ] **Step 2: Run the tests and watch them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Commit and push** on `m10-trace`. Open the `m10-format-v2` and `m10-trace` PRs.

### Task 10: the raw-frame callback, boundary clearing and rgb6

**Files:**
- Modify: `include/vgacap/frame.h`, `src/frame/frame.c`.
- Test: `tests/test_frame_raw.c` (new).

**Interfaces:**
- Produces:

```c
typedef struct vgaframe_raw {
    const uint8_t *raw;      // max_clocks_per_line bytes per row; 6-bit colour | 0x80 written
    uint32_t stride;         // max_clocks_per_line
    uint32_t lines;          // rows this frame received (y + 1), capped at max_lines
    const vgaframe_timing_t *timing;  // the learner's, at the boundary
    uint8_t  retroactive;    // 1 for a frame claimed with report 3 (rows below vsync_lines unwritten)
} vgaframe_raw_t;
typedef void (*vgaframe_raw_fn)(void *user, const vgaframe_raw_t *r);
// in vgaframe_config_t, after `user`:  vgaframe_raw_fn on_raw; void *raw_user;
// in vgaframe_output_t: const uint8_t *rgb6;  // NULL unless a buffer is set
void vgaframe_set_rgb6_buffer(vgaframe_t *f, uint8_t *rgb6);   // vgaframe_raw_size() bytes
```

  At every report 2, while `in_frame`:
  1. call `on_raw` (whatever the lock, mode and content);
  2. run the existing `emit` decision unchanged;
  3. clear `raw` rows `0 .. min(y + 1, max_lines - 1)` and all of `cover`, whether or not `emit` ran.

  `emit`'s own FRAM-mode `clear_lines` stays. `emit` fills `rgb6` beside `rgb24` (an unwritten pixel is 0 in rgb6, and magenta in rgb24 as today). The existing callers zero `vgaframe_config_t` with `memset` (`vgacap_frames.c:88-89`, `gstvgadecode.c:438-439`), so the new fields default to off.

- [ ] **Step 1: Write the failing tests.**
  - `raw_fires_without_lock`: on a stream of two frames of a timing in no table (cpl 801, 525 lines), `on_frame` fires 0 times and `on_raw` fires once for the completed frame, with `lines == 525`.
  - `raw_fires_for_black`: an all-black 801-clock stream (no mode) fires `on_raw` once per completed frame.
  - `shorter_second_frame_clean`: frame A has 525 lines all lit, and frame B 520 lines. In B's callback, rows 520..524 have no written bit.
  - `retroactive_first_frame`: a stream starting mid-frame. The first `on_raw` has `retroactive == 1`, and rows `0 .. vsync_lines - 1` unwritten.
  - `rgb6_matches_rgb24`: for a synth 640x480@60 picture with every 6-bit colour, each `rgb6[i] == (r/85) << 4 | (g/85) << 2 | (b/85)` of `rgb24[3i..]`.
  - `existing_emit_unchanged`: the existing `test_frame` and `test_frame_partial` suites pass unmodified.
- [ ] **Step 2: Run the tests and watch them fail.**
- [ ] **Step 3: Implement.** The raw callback runs before `emit`, because `emit` clears the buffer. Add to `frame.h`: "The raw frame is valid only during the callback; it is cleared at every frame boundary."
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Commit and push** on `m10-frame-raw`.

### Task 11: learner coverage for simulation timings

**Files:**
- Test: `tests/test_timing_sim.c` (new); `tests/synth.c` gains `synth_frame_hvsync()`.

**Interfaces:**
- Produces: `size_t synth_frame_hvsync(const vgaframe_mode_t *m, uint8_t (*pixel)(void *, uint16_t, uint16_t), void *user, uint32_t *out, size_t out_len)`. It models tt-vga-testpatterns' `common/hvsync_generator.v`:
  - hsync pulse when `H_ACTIVE + H_FRONT ≤ hpos < … + H_SYNC`;
  - vsync on `vline`, which is `vpos + 1` (wrapping) once `hpos ≥ H_ACTIVE + H_FRONT`, otherwise `vpos`;
  - both from the same registered positions.

  So vsync changes on the very clock hsync starts. The stream starts at `hpos = vpos = 0`.

- [ ] **Step 1: Write the tests.**
  - `learner_762`: mode `{h 610, 15, 91, 46; v 480, 10, 2, 33}` (762 clocks per line). After 3 frames, `clocks_per_line == 762`, `hsync_width == 91`, `lines_per_frame == 525` and `locked == 1`.
  - `learner_3584`: `{h 2560, 64, 256, 704; v 480, 10, 2, 33}`, buffer `max_clocks_per_line = 7596`, `max_lines = 1200`. Expect `clocks_per_line == 3584`, `hsync_width == 256` and `locked == 1`.
  - `hvsync_row0`: 640x480@60 via `synth_frame_hvsync`, `on_raw` collecting. Row 0 of each frame is the first line whose hsync trailing edge sees vsync in its pulse: the raw row `v_sync + v_back` holds `vpos = 0`'s pixels, starting at x = `h_sync + h_back`. Any error here is fixed in libvgaframe's learner, not in a sampler.
- [ ] **Step 2: Run the tests.** They should pass on the current learner. If one fails, stop and take the failure to the reviewing session before changing `timing.c`.
- [ ] **Step 3: Commit and push** on `m10-frame-raw`. Open the PR.

### Task 12: shared calibration and the frame clock

**Files:**
- Create: `include/vgacap/sample.h`, `src/sample/calib.c`, `src/sample/frameclock.c`; `python/vgacap/calib.py`.
- Modify: `CMakeLists.txt`: library `vgacap_sample` (links `vgacap_frame`, `vgacap_trace`, `vgacap_sha256`, `vgacap_zstd`).
- Test: `tests/test_calib.c`, `python/tests/test_calib.py`, `python/vgacap/synthtrace.py`.

**Interfaces:**
- Produces:

```c
typedef struct vgacal_sync { uint8_t found, active_low; uint64_t pulse, period; } vgacal_sync_t;
enum { VGACAL_RUNNING, VGACAL_DONE };
typedef struct vgacal {          // port of tb.cpp:191-230 and 361-378
    double clock_hz, calib_seconds;
    uint64_t calib_limit;        // (uint64_t)(calib_seconds * clock_hz), as tb.cpp:364
    int state; int started;      // started: rst_n has been seen high
    uint64_t capture_after_clock;   // valid when state == VGACAL_DONE
    vgacal_sync_t hs, vs;
    uint64_t h_phases, v_phases;    // SyncTracker phase counts
    /* tracker internals: last level, phase_start, growable arrays of phase lengths by level */
} vgacal_t;
void vgacal_init(vgacal_t *c, double clock_hz, double calib_seconds);
// Feeds `clocks` clocks starting at clock `first`, all with this clk-high uo_out
// and rst_n. Returns how many it consumed (fewer only when calibration ended inside).
uint64_t vgacal_push(vgacal_t *c, uint8_t uo_out, uint8_t rst_n, uint64_t first, uint64_t clocks);
void vgacal_end_of_trace(vgacal_t *c, uint64_t clocks_in_trace);  // trace ended first
void vgacal_free(vgacal_t *c);

typedef struct vgafc {           // frame clock
    uint8_t v_active_low, prev_v;
    uint64_t *ends; size_t n, cap;  // ends[k]: clock of frame k's vsync end
} vgafc_t;
void vgafc_init(vgafc_t *fc, const vgacal_t *c);        // prev_v = 0, as tb.cpp:480
void vgafc_push(vgafc_t *fc, uint8_t uo_out, uint64_t first, uint64_t clocks);
void vgafc_free(vgafc_t *fc);
```

  - **The calibration port.** Calibration processes clock `c` iff `rst_n` has been 1 at a clk-high sample (`c ≥ 10` for `tb.cpp`'s stimulus) and `c < calib_limit`. For a processed clock, let `T = c + 1` (`tb.cpp`'s `clock` after the tick). It then:
    1. feeds both trackers at `T`;
    2. if `(T & 0xFFFF) == 0`, analyses both and stops when both are found and the vsync tracker has at least 8 phases;
    3. stops when the hsync tracker has more than 4,000,000 phases.

    When it stops, `capture_after_clock = T`. Running out of clocks (`c == calib_limit`) gives `capture_after_clock = calib_limit`, after a final `analyse`. Within one run, the phases cannot change, so at most one analysis per run is needed; the result must equal per-clock processing.
  - **The frame clock.** An end is clock `e ≥ capture_after_clock + 1` with vsync in its pulse at `e - 1` and not at `e` (polarity from `vs.active_low`).
  - **Python.** `calib.py` mirrors both, per clock, as a plain loop over `uo_out[c]`, with no runs.
  - **`synthtrace.py`** builds per-clock `uo_out`, `rst_n` and the 43-bit samples. Its timing options are:
    - any mode, polarity and clocks per pixel (fractional allowed: the design's pixel `p` covers clocks `[floor(p * cpp), floor((p + 1) * cpp))`);
    - the sync phase: `vesa` (syncs exactly on VESA positions), `testpatterns` (tt-vga-testpatterns' `hvsync_generator`, as Task 11's `synth_frame_hvsync`), or `playground` (the VGA Playground's module, which computes the registered syncs from the pre-increment position, so the hsync leading edge is on hpos 657 and vsync changes at the hpos wrap, as `common/hvsync_generator.v:18-27` describes);
    - non-standard porches;
    - glitches (a list of (clock, length) pulses forced onto vsync or hsync);
    - a pixel function.

    It also writes a plain VGCH v2 `RUNS` trace, with the opening and closing `META`, through `vgacap.stream.Writer`.

- [ ] **Step 1: Write the failing tests.** All of them use `synthtrace` with `clock_hz = 25175000`, `calib_seconds = 0.1` (limit 2,517,500) and 10 reset clocks, unless stated.
  - `calib_640x480_vectors`: `hs = {found, active_low, pulse = 96, period = 800}` and `vs = {found, active_low, pulse = 1600, period = 420000}`. `capture_after_clock` equals the Python reference's, and is the first multiple of 65,536 at or after the clock where the 8th vsync phase is complete (computed in the test from the timing).
  - `calib_polarities`: all four polarity combinations give the right `active_low` pair.
  - `calib_no_sync`: constant `uo_out` ends at `calib_limit` with neither found.
  - `calib_glitchy_hsync`: hsync toggling every 2 clocks stops after 4,000,001 phases, at the same clock in C and Python.
  - `calib_run_equals_clock`: C fed per clock, and fed as runs, give identical `vgacal_t` results.
  - `fc_counts`: on 6 frames, `ends[k] - ends[k-1] == 420000`. `ends[0]` is the first end after `capture_after_clock`.
  - `fc_end_on_capture_clock_not_counted`: a vsync pulse ending exactly at `capture_after_clock` is not counted (`tb.cpp:480`).
  - `fc_glitch_adds_end`: a 1-clock vsync glitch inside the pulse adds one end.

  Python and C must agree on every case: `test_calib.py` runs the C through a new test helper `build/vgacap-calib-dump TRACE`, which prints `capture_after_clock`, both syncs and every end, and compares it with `calib.py`.
- [ ] **Step 2: Run the tests and watch them fail.**
- [ ] **Step 3: Implement.** The `median` is the element at `size / 2` after sorting (`tb.cpp:205-209`). `analyse` skips the first phase (`tb.cpp:221`) and needs three of each level.
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Commit and push** on `m10-samplers`.

### Task 13: the samplers `tb-v1` and `centre-v1`

**Files:**
- Create: `src/sample/tbv1.c`, `src/sample/centrev1.c`; extend `sample.h`.
- Create: `python/vgacap/tbv1.py`, `python/vgacap/centre.py`.
- Test: `tests/test_tbv1.c`, `tests/test_centrev1.c`, `python/tests/test_samplers.py`.

**Interfaces:**
- Produces:

```c
typedef struct vgasample_frame {
    uint64_t number;        // frame number from the frame clock
    uint64_t start_clock;   // per sampler, as the spec defines
    const uint8_t *rgb6; uint16_t width, height;
    uint32_t missing;       // centre-v1 only
} vgasample_frame_t;
typedef void (*vgasample_frame_fn)(void *user, const vgasample_frame_t *f);

typedef struct vgasample_geometry {     // fixed at capture_after_clock
    int ok;                 // 0: no picture
    const char *status;     // "no-sync" or "bad-timing" when !ok
    const char *mode;       // table name or "unknown"
    double cpp; uint16_t width, height;
    int hback, vback;       // pixels / lines used (centre-v1: hback', vback')
} vgasample_geometry_t;

typedef struct tbv1 tbv1_t;   // opaque, heap
tbv1_t *tbv1_create(const vgacal_t *cal, const vgafc_t *fc, double clock_hz, double seconds,
                    vgasample_frame_fn fn, void *user);
const vgasample_geometry_t *tbv1_geometry(const tbv1_t *s);
void tbv1_push(tbv1_t *s, uint8_t uo_out, uint64_t first, uint64_t clocks);   // clocks >= capture_after_clock
void tbv1_free(tbv1_t *s);

typedef struct centrev1 centrev1_t;   // opaque, heap; owns its libvgaframe buffers
centrev1_t *centrev1_create(int dx, int dy, vgasample_frame_fn fn, void *user);
void centrev1_push(centrev1_t *s, uint8_t uo_out, uint64_t first, uint64_t clocks);  // every clock from 0
void centrev1_calibrated(centrev1_t *s, const vgacal_t *cal, const vgafc_t *fc);
const vgasample_geometry_t *centrev1_geometry(const centrev1_t *s);
typedef struct centrev1_diag {
    uint64_t outside; int suggest_dx, suggest_dy;
    uint64_t colour_changes, off_grid;   // off_grid only for whole cpp; else UINT64_MAX
    int dx, dy;                          // the override used
} centrev1_diag_t;
void centrev1_finish(centrev1_t *s, centrev1_diag_t *d);   // end of trace: computes diagnostics
void centrev1_free(centrev1_t *s);
```

  **`tb-v1`** ports `tb.cpp:379-557` with its own copy of `tb.cpp`'s 11-mode table, in `tb.cpp`'s order. Specifically:
  - `bad-timing` when `hs.period == 0 || vs.period < 2 * hs.period`, and the 16..4096 size check;
  - mode match with `best = 0.03`, then the fallback loop;
  - `cpp` rounding within 0.01;
  - `target_frames = (uint64_t)(seconds * fps + 0.5)`;
  - `clock_limit = capture_after_clock + (uint64_t)((seconds + 2.5 / fps) * clock_hz)`;
  - clocks processed from `capture_after_clock` while `frames < target_frames && clock < clock_limit`;
  - frame `k` starts at the clock where `prev_v && !v_pulse` (end `k`), and is emitted at end `k + 1`;
  - lines on `prev_h && !h_pulse`;
  - pixels by evaluating `(int)((x_clock + half) / cpp)` per clock in the active area, exactly as `tb.cpp:541-553`, storing rgb6.

  Run arithmetic may skip clocks where `!in_frame`, where `h_pulse` holds, or where the row is outside the picture, but nothing else.

  **`centre-v1`:**
  - **libvgaframe setup.** It runs libvgaframe with `max_clocks_per_line = 7596` and `max_lines = 1200`, the Tiny VGA signal map, `on_raw` set, and an rgb24 buffer of `vgaframe_rgb_size`.
  - **Clock tracking.** It records, per row of the current frame, the clock of each report's push (the hsync trailing edge). That gives the frame start, `trailing_edge_clock(row 0) - report_x`, and for report 3, `trailing - report_x - vsync_lines * clocks_per_line`.
  - **At `centrev1_calibrated`** (line period `L = hs.period`, `lines = round(vs.period / L)` as `tb.cpp:403`):
    - **Mode:** `tb.cpp`'s summed-error rule against the shared 12-mode table, in table order (`vgaframe_modes`), including the `0.9..4.5` range and the non-standard-line-count fallback.
    - **cpp:** `cpp_l = L / mode cpl`. If `|cpp_l - round(cpp_l)| < 0.01`, then `cpp = round(cpp_l)`. Otherwise, if some `k ≥ 1` has `|hs.pulse - k * mode.h_sync| ≤ 2`, then `cpp = k`, the smallest such `k`. Otherwise `cpp = cpp_l`.
    - **Window:** `hsync = hs.pulse / cpp`, `B = L / cpp - hsync - width`, `hback' = floor(B * hback / (hback + hfront) + 0.5)`, and the same vertically with `vpulse_lines` and `lines`. Then add `dx`/`dy`.
    - **Unknown mode:** `tb.cpp:441-444`.
    - **Bad timing** when the frame has more than 1,200 lines.
  - **Pixel pick** in the raw callback: pixel `(p, y)` is raw row `vsync_lines + vback' + y`, at clock `x = (uint32_t)floor((hsync + hback' + p + 0.5) * cpp)`, evaluated as written, with `hsync` in pixels as a double. Unwritten means missing: stored as 0, and counted.
  - **Attach:** take the latest frame-clock end in `[start_clock, trailing_edge_clock(row vsync_lines)]`. With none, the frame is dropped (its number stays a gap).
  - **Activity map:** a 1-bit map of clock positions `(x, row)` that were ever non-black, filled from `raw` in the callback. At the end, `outside` is the lit positions outside the window. `suggest` is the offset `(dx, dy)` that keeps the window inside the line and frame and minimises `outside`; ties go to the smallest `|dx| + |dy|`, then the smallest `dy`, then the smallest `dx`. Two-dimensional prefix sums over the measured `L x lines` make this one pass.
  - **Colour changes:** the clocks inside the window where `uo_out`'s colour changes from the previous clock. `off_grid` is those not at a pixel boundary of the window, for whole `cpp` only.

  Python `tbv1.py` is a per-clock reference of the same port. `centre.py` takes a clock-resolution frame (rows of 6-bit colour plus a written flag, as libvgaframe's `raw`) and the calibration numbers, and returns the window and the picked rgb6. It does not re-implement the learner.

- [ ] **Step 1: Write the failing tests.** Each uses `synthtrace` streams of 7 frames.
  - `tbv1_matches_python`: 640x480@60 at cpp 1, 800x600@72 at cpp 1, and 640x480@60 at cpp 2, 1.90625 and 0.9524 (800-clock lines). C frames equal `tbv1.py`'s byte for byte. Geometry: `mode` names, `cpp` printed with `vgacap_fmt_double` as `"1"`, `"2"`, `"1.90625"` and `"0.95238095238095233"`.
  - `tbv1_reproduces_half_pixel_early`: at cpp 2 with distinct colours per pixel, `tb-v1`'s pixel `p` equals the design's pixel `p - 1`, for `p ≥ 1` in each row. This is the published behaviour, recorded.
  - `tbv1_frame_target`: `seconds = 0.1` at 60 fps stops after `(uint64_t)(0.1 * fps + 0.5)` frames.
  - `tbv1_tennis_lines`: 640x480 timing with 506 lines gives `height = 506 - vpulse_lines` and `vback = 0`.
  - `centre_cpp_rule`:
    - 832-clock lines with a 96-clock hsync and 525 lines give `640x480@60` and cpp 1, by step 2, and `hback' = 72` (nyan; `B = 96`);
    - 800 with 64 and 500 lines give `640x480@75` and cpp 1, by step 2 (rle_vga; `B = 96`);
    - 3,584 with 256 and 500 lines give `640x480@75` and cpp 4 (mandelbrot);
    - 800 with 97 and 525 lines give cpp 1, by step 1;
    - 1,525 with 183 and 525 lines give cpp 1.90625 (fractional, by step 3).
  - `centre_pixel_exact`: for cpp 1, 2, 1.90625 and 0.95, with standard porches and a pixel function unique per pixel, every captured frame equals the design's picture exactly. `missing == 0`, `outside == 0`, `suggest == (0, 0)`.
  - `centre_testpatterns_phase`: the `testpatterns` phase at cpp 1 is pixel-exact, with `outside == 0` and `suggest == (0, 0)`.
  - `centre_playground_phase`: the `playground` phase at cpp 1, with content filling the active area. The window does not move, and the frames are the design's picture shifted by one pixel and one line. `outside` equals the lit clocks of the design's last column and last row. The prediction is `suggest == (-1, -1)`: the line starts one clock late and row 0 one line late, so the content sits one pixel left and one line up of the window. With `dx = -1, dy = -1`, the frames are pixel-exact. If the test shows another offset, stop and settle the reasoning with the reviewing session before changing either side.
  - `centre_override`: `dx = 3, dy = -2` moves the picked window by 3 pixels and -2 lines.
  - `centre_numbers_match_frame_clock`: every centre-v1 frame's number `k` satisfies `ends[k] ∈ [start_clock, row-v trailing edge]`, and frames are numbered as `tb-v1`'s where both exist.
  - `test_centre_glitch_gap`: a 1-clock vsync glitch inside frame 3's pulse. `tb-v1` numbers frames as `tb.cpp` does (one extra number). In `centre-v1` the earlier of the two numbers has no frame. Later frames carry the same numbers in both samplers.
  - `centre_ignores_frames_before_capture`: no frame is attached to a number from before `capture_after_clock`.
  - `centre_drops_cut_last_frame`: the last, unfinished frame is not emitted.

  `test_samplers.py` cross-checks `centre.py`'s window and pick against `centrev1` through a C test helper `build/vgacap-centre-dump`, which writes the raw frame, the geometry and the picked rgb6.
- [ ] **Step 2: Run the tests and watch them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Commit and push** on `m10-samplers`.

### Task 14: hash methods

**Files:**
- Create: `src/sample/hashes.c`; extend `sample.h`.
- Create: `python/vgacap/hashes.py`.
- Test: `tests/test_hashes.c`, `python/tests/test_hashes.py`.

**Interfaces:**
- Produces:
  - `void vgahash_sha256_rgb6(const uint8_t *rgb6, size_t n, uint8_t out[32])`.
  - `uint64_t vgahash_fnv1a64_tb2026_rgb888(const uint8_t *rgb6, size_t n)`: FNV-1a 64 over RGB888 bytes (each channel times 85), prime `0x100000001b3`, offset basis `0x14650fb0739d0383`.
  - `const char *const *vgahash_definition(const char *method)`: the comment lines below, NULL-terminated.

  The definitions, copied verbatim into every hash file as `# ` lines:
  - **`sha256-rgb6`:** `SHA-256 of the frame as rgb6: one byte per pixel, R<<4 | G<<2 | B,` and `row-major, active area only, at native resolution.`
  - **`fnv1a64-tb2026-rgb888`:** `FNV-1a 64 loop (prime 0x100000001b3) with a NON-STANDARD offset basis,`, then `hash_offset_basis below, not 0xcbf29ce484222325: tb.cpp's constant lost a digit.`, then `Over the frame as RGB888, row-major, active area only, at native resolution,` and `each 2-bit channel stored as value * 85.`

- [ ] **Step 1: Write the failing tests.**

  | rgb6 input | `sha256-rgb6` | `fnv1a64-tb2026-rgb888` |
  | --- | --- | --- |
  | bytes 0..7 | `8a851ff82ee7048ad09ec3847f1ddf44944104d2cbd17ef4e3db22c6785a0d45` | `760bbc7b258ddb8b` |
  | 640x480 zero | `7818f5542a0404157573be6cffc0e0c8e68ce3c0f5d17d07ccdd9313fb700baf` | `009b538b2455c383` (the black frames in tt07 `tt_um_MichaelBell_rle_vga`'s published hashes) |
  | 640x480 of `i % 64` | `9cc7a2f413ef0ebe2541f5de1d77972dd92241ffff0c1b5f72279fc23608e8c6` | `9d900346f0fe6783` |

  Python computes the same with `hashlib` and a plain loop.
- [ ] **Step 2: Run the tests and watch them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Commit and push** on `m10-samplers`.

### Task 15: frames.txt and hash files (formats and the Python reader)

**Files:**
- Create: `src/sample/outputs.c` (writers); `python/vgacap/framesfile.py` (reader, and a writer the tests use as the reference); `docs/frames-format.md`.
- Test: `tests/test_outputs.c`, `python/tests/test_framesfile.py`.

**Interfaces:**
- Produces: the file formats below; C writers `vgaout_frames_txt(FILE *, const vgaout_t *)` and `vgaout_hash_file(FILE *, const char *method, const vgaout_t *)`, where `vgaout_t` holds the header values, the distinct SHA-256 list and the per-frame records (`number`, `distinct` or −1 for a gap, `start_clock`, `missing`); Python `read_frames_txt(path) -> FramesFile`, `read_hash_file(path) -> HashFile`, and writers.

  **`frames.txt`.** The header is `key: value` lines in this order:
  - `id`, `status`, `sampler`, `pixel_format: rgb6`, `width`, `height`, `mode`, `clock_hz`, `clocks_per_pixel`, `capture_after_clock`, `frame_clocks`, `frames`, `distinct_frames`, `store`, `store_length`, `store_sha256`;
  - for `centre-v1` only, `window_offset: <dx> <dy>`, `porches: <hback'> <vback'>`, `outside: <n>`, `suggested_offset: <dx> <dy>`, `colour_changes: <n>`, `colour_changes_off_grid: <n|->`.

  Then a line `distinct:`, followed by one lowercase SHA-256 per distinct frame in store order. Then a line `runs:`, followed by run lines:
  - a frame run is `<first frame> <count> <distinct> <start clock> <missing>`;
  - a gap run is `<first frame> <count> - - -`.

  A run continues while the distinct number and `missing` stay the same and each start is exactly `frame_clocks` after the previous one. `frame_clocks` is the median (element `size / 2` after sorting) of the distances between consecutive non-gap frame starts, or 0 with fewer than two frames.

  **`frame_hashes.<method>.txt`:**
  - line 1 is `hash_method: <id>`;
  - then the definition as `# ` lines;
  - then the parameters (`hash_offset_basis: 0x14650fb0739d0383` for the FNV method; none for SHA);
  - then `id`, `status`, `sampler`, `mode`, `width`, `height`, `clock_hz`, `clocks_per_pixel`, `capture_after_clock`, `frames`;
  - then one line per frame, frame 0 first: 16 hex digits (FNV) or 64 (SHA), or `-` for a gap.

- [ ] **Step 1: Write the failing tests.**
  - `runs_grouping`: frames with distinct numbers `0 0 0 1 1 gap gap 0` and regular starts give runs `0 3 0 …`, `3 2 1 …`, `5 2 - - -`, `7 1 0 …`.
  - `runs_break_on_late_start`: the same distinct frame starting `frame_clocks + 1` late begins a new run.
  - `runs_break_on_missing`: a change in `missing` begins a new run.
  - `hash_file_lines`: line `k + header_lines` is frame `k`, and gaps are `-`.
  - The Python reader reads C-written files back into identical records, and the Python writer produces byte-identical files from those records.
- [ ] **Step 2: Run the tests and watch them fail.**
- [ ] **Step 3: Implement.** Write `docs/frames-format.md` with the formats above.
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Commit and push** on `m10-samplers`. Open the PR.

### Task 16: `vgacap-sample`

**Files:**
- Create: `src/tools/vgacap_sample.c`.
- Modify: `pyproject.toml`: add `zstandard>=0.23` to the `dev` group, so the tests can read stores on Python 3.11-3.13. On 3.14 the tests use `compression.zstd`.
- Test: `python/tests/test_vgacap_sample.py`.

**Interfaces:**
- Consumes: Tasks 9, 12-15.
- Produces:
  - **Command line:** `vgacap-sample TRACE --out DIR --name PREFIX [--sampler tb-v1] [--sampler centre-v1] [--centre-window DX,DY] [--store-level N] [--png-fd FD]`.
    - Default: both samplers.
    - `--store-level` defaults to 3.
    - Exit codes: 0 when everything requested was written (including no-picture runs, which write `frames: 0` files); 2 for usage errors; 1 for I/O or trace errors (message on stderr).
  - **Per sampler, `DIR/<sampler>/`:**
    - `PREFIX_<sampler>_frames.rgb6.zst`: one zstd stream of distinct frames in first-appearance order, with `ZSTD_c_enableLongDistanceMatching = 1` and `ZSTD_c_windowLog = 27`;
    - `frames.txt`;
    - `frame_hashes.sha256-rgb6.txt`;
    - for `tb-v1` only, `frame_hashes.fnv1a64-tb2026-rgb888.txt`.
  - **Run parameters:** `clock_hz`, `calib_seconds`, `seconds` and `id` come from `META(open)` (doubles parsed with `strtod`). `status` comes from `META(close)`, or is `truncated` when that chunk is absent.
  - **One pass.** One `vgacap_trace_read` over the whole trace feeds, per run of clk-high samples:
    1. the calibration;
    2. then, from `capture_after_clock`, the frame clock;
    3. then both samplers.

    `centre-v1` is fed from clock 0. Runs of half-clock samples are turned into runs of clk-high samples (sample `2c + 1`); a run that covers only clk-low samples contributes nothing.
  - **PNG pipe (`--png-fd`).** Each new distinct frame is written as a text line `<sampler> <distinct> <width> <height>\n`, followed by `width * height` rgb6 bytes. It is written before the frame's store bytes.

- [ ] **Step 1: Write the failing tests.** They use `synthtrace` traces:
  - `test_sample_both`: a 640x480@60, cpp 1 design with a changing picture gives the files above.
    - `frames.txt` equals the Python reference's frames file (from `tbv1.py`/`centre.py` and `framesfile.py`) byte for byte.
    - The store decompresses with Python's `zstandard` (dev group) or `compression.zstd`, whichever the interpreter has, to the distinct frames whose SHA-256s are listed.
    - `store_sha256` matches.
  - `test_sample_png_pipe`: reading `--png-fd`'s records gives exactly the distinct frames, in order, for both samplers.
  - `test_sample_truncated`: a trace cut as in Task 9 gives `status: truncated`, and the frames of the complete blocks only.
  - `test_sample_ends_in_calibration`: a trace of 50,000 clocks (inside calibration) exits 0, with both `frames.txt` files saying `frames: 0` and `distinct_frames: 0`, and `status` from the trace.
  - `test_sample_no_sync`: constant `uo_out` gives `status` from the trace and `mode: unknown`, `frames: 0`.
  - `test_sample_centre_window`: `--centre-window 2,1` is recorded as `window_offset: 2 1`.
  - `test_sample_one_pass`: with `VGACAP_SAMPLE_DEBUG=1` the tool prints `trace_passes=1 blocks_decoded=<n>` to stderr, and `n` equals the trace's block count, whichever samplers are requested.
- [ ] **Step 2: Run the tests and watch them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Measure.** Time `vgacap-sample` on a synthetic 1.5e9-clock busy trace (from `bench-runs`' busy profile written through the trace writer). Append ns per clock to the Task 2 research note, against the 11 ns/clock budget.
- [ ] **Step 6: Commit, push and open the PR** on `m10-sample-tool`.

### Task 17: `vgacap-export` (FST, VCD and viewer files)

**Files:**
- Create: `src/tools/vgacap_export.c`; `tests/vectors/export_small.vcd` (committed expected output).
- Test: `python/tests/test_vgacap_export.py`, `tests/test_export_fst.c`.

**Interfaces:**
- Produces:
  - **Command line:** `vgacap-export TRACE --out FILE [--format fst|vcd] [--from CLOCK] [--to CLOCK] [--no-clk] [--sampler ID --frames FRAMES_TXT] [--scope NAME]`. The default format is from the extension, else FST. `--from`/`--to` are clocks (from inclusive, to exclusive), converted to samples by `samples_per_clock`.
  - **Timescale and time:** 1 ps; times from `vgacap_sample_time_ps(n, …)` of the absolute sample number.
  - **Scopes for `layout=tt-um-43` traces:**
    - `<scope>` (default the trace's `project` key with `/` replaced by `_`, else `trace`) holds `clk`, `rst_n`, `ena`, `ui_in[7:0]`, `uio_in[7:0]`, `uo_out[7:0]`, `uio_out[7:0]` and `uio_oe[7:0]`;
    - `<scope>.decoded` holds `hsync`, `vsync`, `r[1:0]`, `g[1:0]`, `b[1:0]`, `rgb6[5:0]`, and `frame[31:0]` with `--sampler`. `frame` holds the frame number from the run lines of `frames.txt` from each start clock, and `-1` (all ones) before frame 0 and in gaps.
  - **Other traces:** `sample[bits-1:0]` (board captures) plus the same decoded scope from the header's signal map.
  - **`--no-clk`** drops `clk`.
  - **VCD:** no `$date`; `$version vgacap-export $end`, so the file is reproducible.
  - **`.gtkw` beside the output** (`FILE` with its extension replaced), as text:
    - `[dumpfile] "<FILE>"`, `[timestart] <from ps>`;
    - a group `ports` (`@800200` / `-ports` … `@1000200` / `-ports`) and a group `decoded`;
    - single bits as `@28`, buses as `@22`, `frame` as `@24`.
  - **Surfer:** check Surfer's documentation at the version in the pinned oss-cad-suite. If it documents a command or state file that loads a waveform and adds signals, write one beside the output with the same signals, and cite the documentation page in `README.md`. If it does not, write none, and say so in `README.md`.

- [ ] **Step 1: Write the failing tests.**
  - `vcd_matches_expected`: a `synthtrace` trace of 3 frames at 640x480 with a 20-clock window (`--from 1310720 --to 1310740`) exports to bytes identical to `tests/vectors/export_small.vcd`. The vector is written by hand from the trace's known pins and checked by reading it, not generated by the tool.
  - `fst_equals_vcd`: `test_export_fst.c` reads the FST with libfst (`fstReaderIterBlocks2`) and the VCD with a small parser in the test, and compares the (time, signal name, value) lists. If `fst2vcd` is on `PATH`, the Python test also runs it and compares the value changes; otherwise it skips with the reason.
  - `range_seeks`: on a multi-block trace, exporting a range in block 3 decodes only blocks 3 and, if the range crosses, 4 (stderr reports `blocks_read=` with `VGACAP_EXPORT_DEBUG=1`).
  - `frame_signal`: with `--sampler centre-v1 --frames frames.txt`, `frame` changes at each frame's start clock to its number.
  - `gtkw_written`: the `.gtkw` names every exported signal once and points at the output.
  - `board_capture_exports`: the v1 fixture exports with a `sample[7:0]` signal and decoded hsync/vsync.
- [ ] **Step 2: Run the tests and watch them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests and see them pass.**
- [ ] **Step 5: Document the format.** Write `docs/trace-format.md`: the VGCH v2 header, `RUNS`/`BLKH`/`META`, the container and its rebuild, the bit layout, the time rule and the clock numbering. It is precise enough to read without vgacap (the spec requires this).
- [ ] **Step 6: Commit, push and open the PR** on `m10-export`.

### Task 18: `tb-v1` test vectors from `tb.cpp` (after the pipeline plan)

**Files:**
- Create: `tests/vectors/tbv1/<case>/{trace.vgch, frame_hashes.fnv1a64-tb2026-rgb888.txt, frames.txt}`, copied from the tinytapeout-vga-videos test that simulates small designs with `tb.cpp`.
- Test: `python/tests/test_tbv1_vectors.py`.

**Interfaces:**
- Consumes: the pipeline plan's `tb.cpp` comparison test. It produces plain-VGCH traces of small synthetic designs, together with `tb.cpp`'s own frame hashes.

- [ ] **Step 1: Write the test.** For each case, `vgacap-sample --sampler tb-v1` on `trace.vgch` gives a `frame_hashes.fnv1a64-tb2026-rgb888.txt` whose hash lines equal the committed file's (which are `tb.cpp`'s), and a `frames.txt` equal to the committed one.
- [ ] **Step 2: Run it.** Expected: it passes. Any difference is a `tb-v1` port bug, fixed in `tbv1.c` and `tbv1.py`, not in the vectors.
- [ ] **Step 3: Commit, push and open the PR.** Tick every Milestone 10 item in tt-vga-capture `TASKS.md`.
