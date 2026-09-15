# Milestone 2: stream formats and reconstruction library — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `vgacap`'s portable C stream encoder/decoder and the `libvgaframe` reconstruction library, with a Python mirror of the stream format and an end-to-end synthetic test that turns a known image into a stream and back into the identical image.

**Architecture:** A chunked binary stream (`VGCH` header, `RAW `, `RLE `, `FRAM`, `EVNT`, `TIME` chunks) is decoded incrementally by `vgacap_reader`, which emits `(value, run)` pairs and frame/timing events through callbacks. `vgaframe` consumes those runs, learns sync polarity and timing, places pixels in a raw sample framebuffer indexed from the sync edges, and on frame completion crops to the active area (mode table or auto-detected) and expands 6-bit colour to RGB24. A small CLI (`vgacap-frames`) writes PPM files so Python tests can compare against reference renders.

**Tech Stack:** C99, CMake ≥ 3.16, ctest with a header-only assert harness; Python 3.11+ via `uv` (numpy, Pillow, pytest) for the mirror implementation and end-to-end tests; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md` in `mithro/tt-vga-capture` (sections 5.1, 5.2, 8).

## Global Constraints

- Apache-2.0; every source file starts with `// SPDX-License-Identifier: Apache-2.0`.
- Core C is C99, no dependencies beyond libc, no allocation after init (callers provide buffers).
- All multi-byte integers in the stream are little-endian.
- Python only through `uv` (`uv run`, `uv add`); never plain `python`/`pip`.
- ISO 8601 dates everywhere.
- Small commits, one logical change each; push after each task.
- Repo: `mithro/vgacap`, local checkout `~/github/TinyTapeout/vgacap`. Sub-agents work in `.worktrees/<branch>` inside it, never on `main`.

## Stream format (normative for this milestone)

Chunk: `tag[4]` ASCII, `u32 length`, `payload[length]`.

`VGCH` payload (header, first chunk):

| offset | type | field |
|---|---|---|
| 0 | u16 | version = 1 |
| 2 | u8 | sample_bits: 8, 12, 16 or 32 |
| 3 | u8 | mode: 0 extclk, 1 selfclk, 2 event, 3 unknown |
| 4 | u32 | clock_hz (0 = unknown) |
| 8 | u8[8] | signal_map: bit index of hsync, vsync, r1, r0, g1, g0, b1, b0; 0xFF = absent |
| 16 | u8 | samples_per_word: 1, 2, 4 or 8 (32-bit words) |
| 17 | u8 | flags: bit0 = first sample of a word is in the most significant position |
| 18 | u16 | desc_len |
| 20 | u8[desc_len] | desc, UTF-8 |

Tiny VGA default signal_map = {7, 3, 0, 4, 1, 5, 2, 6}.

`RAW ` payload: `u32 sample_count`, then `ceil(sample_count / samples_per_word)` u32 words. Sample i lives in word `i / spw`; within the word at bit position `(i % spw) * sample_bits` when flags bit0 is clear, or `(spw - 1 - i % spw) * sample_bits` when set. Bits above `sample_bits` in a slot are ignored.

`RLE ` payload: `u32 pair_count`, then pairs `(u32 value, u32 run)`.

`FRAM` payload: `u32 frame_counter`, `u16 first_line`, `u16 line_count`, `u32 clocks_per_line`, `u32 sample_count`, then words as `RAW `. The samples start at the leading edge of the hsync pulse of `first_line`.

`EVNT` payload: `u32 event_count`, then `(u64 clock, u32 value)` pairs; clock strictly increasing; value holds until the next event.

`TIME` payload: `u64 host_time_ns`, `u32 clock_hz`, `u32 dropped_samples`, `u16 msg_len`, `u8[msg_len] msg`.

The spec text "run length width fixed by the header" is superseded: runs are always u32 (Task 4 updates the spec).

## File structure

```
vgacap/
  LICENSE  README.md  .gitignore  CMakeLists.txt  pyproject.toml
  .github/workflows/ci.yml
  include/vgacap/stream.h        chunk tags, header struct, writer and reader API
  include/vgacap/frame.h         vgaframe API, timing struct, mode table entry
  src/stream/writer.c            vgacap_writer_*: header, RAW, RLE, FRAM, EVNT, TIME
  src/stream/reader.c            vgacap_reader_*: incremental chunk parser, run emission
  src/frame/modes.c              built-in mode table and matching
  src/frame/timing.c             sync polarity and period learning
  src/frame/frame.c              pixel placement, frame completion, RGB24 output
  src/tools/vgacap_dump.c        CLI: print header, chunk list, sample count, sample CRC32
  src/tools/vgacap_frames.c      CLI: stream file -> frame-NNNN.ppm
  tests/harness.h                assert macros, test registry
  tests/test_stream_header.c  tests/test_stream_raw.c  tests/test_stream_chunks.c
  tests/test_modes.c  tests/test_timing.c  tests/test_frame.c  tests/test_frame_partial.c
  tests/synth.h  tests/synth.c   C synthetic stream generator shared by tests
  python/vgacap/__init__.py  python/vgacap/stream.py  python/vgacap/synth.py  python/vgacap/ppm.py
  python/tests/test_stream.py  python/tests/test_roundtrip_c.py  python/tests/test_frames_e2e.py
```

---

### Task 1: Repository skeleton, build, CI, GitHub repo

**Files:**
- Create: `LICENSE`, `README.md`, `.gitignore`, `CMakeLists.txt`, `tests/harness.h`, `tests/test_harness_smoke.c`, `.github/workflows/ci.yml`, `pyproject.toml`, `python/vgacap/__init__.py`, `python/tests/test_import.py`

**Interfaces:**
- Produces: `tests/harness.h` macros `TEST(name)`, `ASSERT_TRUE(x)`, `ASSERT_EQ_U(a,b)`, `ASSERT_EQ_MEM(a,b,n)`, `RUN_TESTS()`; CMake function `vgacap_add_test(name)`.

- [ ] **Step 1: Create the repo and skeleton files**

```bash
mkdir -p ~/github/TinyTapeout/vgacap && cd ~/github/TinyTapeout/vgacap && git init -q -b main
curl -sfL https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE
printf 'build/\n.worktrees/\ntmp/\n__pycache__/\n*.pyc\n.venv/\n.pytest_cache/\n' > .gitignore
```

`tests/harness.h`:

```c
// SPDX-License-Identifier: Apache-2.0
#ifndef VGACAP_TEST_HARNESS_H
#define VGACAP_TEST_HARNESS_H
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static int harness_failures = 0;
static int harness_tests = 0;

#define ASSERT_TRUE(x) do { if (!(x)) { harness_failures++; \
    fprintf(stderr, "  FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); return; } } while (0)
#define ASSERT_EQ_U(a, b) do { unsigned long long _a = (unsigned long long)(a), _b = (unsigned long long)(b); \
    if (_a != _b) { harness_failures++; \
    fprintf(stderr, "  FAIL %s:%d: %s == %llu, expected %s == %llu\n", __FILE__, __LINE__, #a, _a, #b, _b); return; } } while (0)
#define ASSERT_EQ_MEM(a, b, n) do { if (memcmp((a), (b), (n)) != 0) { harness_failures++; \
    fprintf(stderr, "  FAIL %s:%d: memory differs: %s vs %s (%zu bytes)\n", __FILE__, __LINE__, #a, #b, (size_t)(n)); return; } } while (0)

#define TEST(name) static void name(void)
#define RUN(name) do { harness_tests++; fprintf(stderr, "RUN  %s\n", #name); name(); } while (0)
#define RUN_TESTS_END() do { fprintf(stderr, "%d tests, %d failures\n", harness_tests, harness_failures); \
    return harness_failures ? 1 : 0; } while (0)
#endif
```

`tests/test_harness_smoke.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "harness.h"
TEST(smoke_passes) { ASSERT_EQ_U(1 + 1, 2); }
int main(void) { RUN(smoke_passes); RUN_TESTS_END(); }
```

`CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.16)
project(vgacap C)
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE RelWithDebInfo)
endif()
add_compile_options(-Wall -Wextra -Werror -Wshadow -Wconversion)
include_directories(include)
enable_testing()

function(vgacap_add_test name)
  add_executable(${name} tests/${name}.c ${ARGN})
  target_include_directories(${name} PRIVATE tests)
  add_test(NAME ${name} COMMAND ${name})
endfunction()

vgacap_add_test(test_harness_smoke)
```

`pyproject.toml`:

```toml
[project]
name = "vgacap"
version = "0.0.1"
description = "Tiny Tapeout VGA capture: stream format mirror, synthetic generators, tests"
requires-python = ">=3.11"
dependencies = ["numpy>=1.26", "pillow>=10"]

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["python/tests"]

[tool.setuptools]
package-dir = {"" = "python"}
packages = ["vgacap"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

`python/vgacap/__init__.py`: `"""vgacap: Tiny Tapeout VGA capture stream tools."""` and `__version__ = "0.0.1"`.

`python/tests/test_import.py`:

```python
import vgacap

def test_import():
    assert vgacap.__version__ == "0.0.1"
```

`.github/workflows/ci.yml`:

```yaml
name: ci
on: [push, pull_request]
jobs:
  c:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cmake -S . -B build && cmake --build build -j && ctest --test-dir build --output-on-failure
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: cmake -S . -B build && cmake --build build -j
      - run: uv run pytest -q
```

`README.md`: title, one paragraph (what vgacap is, link to `mithro/tt-vga-capture` for the design), "AI in use" caution, build instructions (`cmake -S . -B build && cmake --build build && ctest --test-dir build`, `uv run pytest`), license line.

- [ ] **Step 2: Build and run the smoke test**

Run: `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure && uv run pytest -q`
Expected: `100% tests passed`, `1 passed`.

- [ ] **Step 3: Commit in pieces, create the GitHub repo, apply standard settings**

```bash
git add LICENSE README.md .gitignore && git commit -m "Initial commit: license, README, gitignore"
git add CMakeLists.txt tests/harness.h tests/test_harness_smoke.c && git commit -m "Add CMake build and C test harness"
git add pyproject.toml python && git commit -m "Add Python package skeleton"
git add .github && git commit -m "Add GitHub Actions CI"
gh repo create mithro/vgacap --public --source=. --remote=origin --push --description "Capture Tiny Tapeout VGA output with RP2/RP1 PIO, reconstruct frames, serve through GStreamer"
git remote set-url origin git@github.com:mithro/vgacap.git
git tag v0.0 $(git rev-list --max-parents=0 HEAD) && git push origin v0.0
```

Then apply the `github-setup` skill's settings (wiki/projects/discussions off, merge commits only, delete branch on merge, secret scanning + push protection, allow_update_branch, main protection, tag ruleset `vXX.ZZZ`).

---

### Task 2: Stream header write and read

**Files:**
- Create: `include/vgacap/stream.h`, `src/stream/writer.c`, `src/stream/reader.c`, `tests/test_stream_header.c`
- Modify: `CMakeLists.txt` (add `vgacap_stream` static library, link tests)

**Interfaces:**
- Produces:

```c
// include/vgacap/stream.h
#define VGACAP_TAG_HEADER "VGCH"
#define VGACAP_TAG_RAW    "RAW "
#define VGACAP_TAG_RLE    "RLE "
#define VGACAP_TAG_FRAME  "FRAM"
#define VGACAP_TAG_EVENT  "EVNT"
#define VGACAP_TAG_TIME   "TIME"
#define VGACAP_DESC_MAX 255
#define VGACAP_FLAG_FIRST_SAMPLE_MSB 0x01

enum vgacap_mode { VGACAP_MODE_EXTCLK = 0, VGACAP_MODE_SELFCLK = 1, VGACAP_MODE_EVENT = 2, VGACAP_MODE_UNKNOWN = 3 };
enum vgacap_signal { VGACAP_SIG_HSYNC = 0, VGACAP_SIG_VSYNC, VGACAP_SIG_R1, VGACAP_SIG_R0, VGACAP_SIG_G1, VGACAP_SIG_G0, VGACAP_SIG_B1, VGACAP_SIG_B0, VGACAP_SIG_COUNT };
#define VGACAP_SIG_ABSENT 0xFF

typedef struct vgacap_header {
    uint16_t version;
    uint8_t  sample_bits;        // 8, 12, 16, 32
    uint8_t  mode;               // enum vgacap_mode
    uint32_t clock_hz;
    uint8_t  signal_map[VGACAP_SIG_COUNT];
    uint8_t  samples_per_word;   // 1, 2, 4, 8
    uint8_t  flags;
    uint8_t  desc_len;
    char     desc[VGACAP_DESC_MAX + 1];
} vgacap_header_t;

void vgacap_header_init_tinyvga(vgacap_header_t *h, uint8_t sample_bits, uint8_t samples_per_word, uint8_t flags);
// sets version=1, mode=UNKNOWN, clock_hz=0, signal_map={7,3,0,4,1,5,2,6}, desc empty

typedef int (*vgacap_write_fn)(void *user, const uint8_t *buf, size_t len); // return 0 on success

typedef struct vgacap_writer {
    vgacap_write_fn write;
    void *user;
    vgacap_header_t header;
    uint8_t scratch[64];
} vgacap_writer_t;

int vgacap_writer_init(vgacap_writer_t *w, vgacap_write_fn write, void *user, const vgacap_header_t *h); // writes the VGCH chunk immediately

typedef enum vgacap_event_type {
    VGACAP_EV_HEADER, VGACAP_EV_RUN, VGACAP_EV_FRAME_BEGIN, VGACAP_EV_TIME, VGACAP_EV_ERROR
} vgacap_event_type_t;

typedef struct vgacap_event {
    vgacap_event_type_t type;
    union {
        const vgacap_header_t *header;
        struct { uint32_t value; uint32_t run; } run;
        struct { uint32_t frame_counter; uint16_t first_line; uint16_t line_count; uint32_t clocks_per_line; uint32_t sample_count; } frame;
        struct { uint64_t host_time_ns; uint32_t clock_hz; uint32_t dropped_samples; const char *msg; uint16_t msg_len; } time;
        struct { const char *what; } error;
    } u;
} vgacap_event_t;

typedef void (*vgacap_event_fn)(void *user, const vgacap_event_t *ev);

typedef struct vgacap_reader {
    vgacap_event_fn cb; void *user;
    vgacap_header_t header; int have_header;
    // chunk parsing state
    uint8_t  tag[4]; uint32_t length; uint32_t consumed; int in_payload; uint8_t hdrbuf[8]; uint8_t hdrfill;
    // payload state (RAW/FRAM word unpack, RLE/EVNT pair assembly)
    uint8_t  pbuf[16]; uint8_t pfill; uint32_t remaining_items; uint32_t sample_index;
    uint64_t last_event_clock; uint32_t last_event_value; int have_last_event;
    char     msgbuf[256];
} vgacap_reader_t;

void vgacap_reader_init(vgacap_reader_t *r, vgacap_event_fn cb, void *user);
int  vgacap_reader_feed(vgacap_reader_t *r, const uint8_t *buf, size_t len); // 0 ok, -1 after an ERROR event
```

- [ ] **Step 1: Write the failing test**

`tests/test_stream_header.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "harness.h"
#include "vgacap/stream.h"

static uint8_t outbuf[4096]; static size_t outlen;
static int capture_write(void *user, const uint8_t *buf, size_t len) {
    (void)user; if (outlen + len > sizeof outbuf) return -1;
    memcpy(outbuf + outlen, buf, len); outlen += len; return 0;
}
static vgacap_header_t seen; static int seen_header;
static void on_event(void *user, const vgacap_event_t *ev) {
    (void)user; if (ev->type == VGACAP_EV_HEADER) { seen = *ev->u.header; seen_header++; }
}

TEST(header_roundtrip) {
    vgacap_header_t h; vgacap_header_init_tinyvga(&h, 12, 2, 0);
    h.clock_hz = 25175000; h.mode = VGACAP_MODE_EXTCLK;
    strcpy(h.desc, "tt07 tt_um_rejunity_vga"); h.desc_len = (uint8_t)strlen(h.desc);
    vgacap_writer_t w; outlen = 0;
    ASSERT_EQ_U(vgacap_writer_init(&w, capture_write, NULL, &h), 0);
    ASSERT_EQ_MEM(outbuf, "VGCH", 4);
    ASSERT_EQ_U(outbuf[4] | (outbuf[5] << 8), 20 + h.desc_len);
    ASSERT_EQ_U(outlen, 8 + 20 + h.desc_len);
    ASSERT_EQ_U(outbuf[8 + 2], 12);           // sample_bits
    ASSERT_EQ_U(outbuf[8 + 8], 7);            // hsync bit
    ASSERT_EQ_U(outbuf[8 + 16], 2);           // samples_per_word

    vgacap_reader_t r; seen_header = 0; vgacap_reader_init(&r, on_event, NULL);
    // feed one byte at a time to prove incremental parsing
    for (size_t i = 0; i < outlen; i++) ASSERT_EQ_U(vgacap_reader_feed(&r, outbuf + i, 1), 0);
    ASSERT_EQ_U(seen_header, 1);
    ASSERT_EQ_U(seen.version, 1);
    ASSERT_EQ_U(seen.sample_bits, 12);
    ASSERT_EQ_U(seen.clock_hz, 25175000);
    ASSERT_EQ_U(seen.signal_map[VGACAP_SIG_B0], 6);
    ASSERT_EQ_U(seen.desc_len, h.desc_len);
    ASSERT_TRUE(strcmp(seen.desc, h.desc) == 0);
}

TEST(header_rejects_bad_version) {
    uint8_t bad[28] = { 'V','G','C','H', 20,0,0,0, 9,0, 8, 3, 0,0,0,0, 7,3,0,4,1,5,2,6, 4, 0, 0,0 };
    vgacap_reader_t r; vgacap_reader_init(&r, on_event, NULL);
    ASSERT_EQ_U(vgacap_reader_feed(&r, bad, sizeof bad), (unsigned long long)-1);
}

int main(void) { RUN(header_roundtrip); RUN(header_rejects_bad_version); RUN_TESTS_END(); }
```

- [ ] **Step 2: Run to verify it fails**

Add to `CMakeLists.txt` before the tests: `add_library(vgacap_stream STATIC src/stream/writer.c src/stream/reader.c)` and change `vgacap_add_test` to `target_link_libraries(${name} PRIVATE vgacap_stream)`. Add `vgacap_add_test(test_stream_header)`. Create empty `src/stream/writer.c` and `reader.c` with only the SPDX line and `#include "vgacap/stream.h"`.

Run: `cmake -S . -B build && cmake --build build`
Expected: link errors for `vgacap_header_init_tinyvga`, `vgacap_writer_init`, `vgacap_reader_init`, `vgacap_reader_feed`.

- [ ] **Step 3: Implement the header**

`src/stream/writer.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "vgacap/stream.h"
#include <string.h>

static void put_u16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void put_u32(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); }

void vgacap_header_init_tinyvga(vgacap_header_t *h, uint8_t sample_bits, uint8_t samples_per_word, uint8_t flags) {
    static const uint8_t tinyvga[VGACAP_SIG_COUNT] = { 7, 3, 0, 4, 1, 5, 2, 6 };
    memset(h, 0, sizeof *h);
    h->version = 1; h->sample_bits = sample_bits; h->mode = VGACAP_MODE_UNKNOWN;
    memcpy(h->signal_map, tinyvga, sizeof tinyvga);
    h->samples_per_word = samples_per_word; h->flags = flags;
}

static int write_chunk_head(vgacap_writer_t *w, const char tag[4], uint32_t length) {
    uint8_t head[8]; memcpy(head, tag, 4); put_u32(head + 4, length);
    return w->write(w->user, head, 8);
}

int vgacap_writer_init(vgacap_writer_t *w, vgacap_write_fn write, void *user, const vgacap_header_t *h) {
    memset(w, 0, sizeof *w); w->write = write; w->user = user; w->header = *h;
    uint8_t *p = w->scratch;
    put_u16(p + 0, h->version); p[2] = h->sample_bits; p[3] = h->mode; put_u32(p + 4, h->clock_hz);
    memcpy(p + 8, h->signal_map, VGACAP_SIG_COUNT); p[16] = h->samples_per_word; p[17] = h->flags;
    put_u16(p + 18, h->desc_len);
    if (write_chunk_head(w, VGACAP_TAG_HEADER, 20u + h->desc_len)) return -1;
    if (w->write(w->user, p, 20)) return -1;
    if (h->desc_len && w->write(w->user, (const uint8_t *)h->desc, h->desc_len)) return -1;
    return 0;
}
```

`src/stream/reader.c` (header handling; later tasks add the other chunk types to `payload_byte`):

```c
// SPDX-License-Identifier: Apache-2.0
#include "vgacap/stream.h"
#include <string.h>

static uint16_t get_u16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t get_u32(const uint8_t *p) { return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }

void vgacap_reader_init(vgacap_reader_t *r, vgacap_event_fn cb, void *user) {
    memset(r, 0, sizeof *r); r->cb = cb; r->user = user;
}

static int fail(vgacap_reader_t *r, const char *what) {
    vgacap_event_t ev; ev.type = VGACAP_EV_ERROR; ev.u.error.what = what; r->cb(r->user, &ev);
    r->in_payload = 0; r->hdrfill = 0; return -1;
}

static int tag_is(const vgacap_reader_t *r, const char *t) { return memcmp(r->tag, t, 4) == 0; }

static int begin_payload(vgacap_reader_t *r) {
    r->consumed = 0; r->pfill = 0; r->sample_index = 0; r->remaining_items = 0;
    if (tag_is(r, VGACAP_TAG_HEADER)) { if (r->length < 20 || r->length > 20 + VGACAP_DESC_MAX) return fail(r, "bad header length"); return 0; }
    if (!r->have_header) return fail(r, "chunk before header");
    return 0; // other tags handled in later tasks; unknown tags are skipped
}

static int end_payload(vgacap_reader_t *r) {
    if (tag_is(r, VGACAP_TAG_HEADER)) {
        const uint8_t *p = r->pbuf; (void)p;
        vgacap_event_t ev; ev.type = VGACAP_EV_HEADER; ev.u.header = &r->header; r->have_header = 1; r->cb(r->user, &ev);
    }
    r->in_payload = 0; r->hdrfill = 0; return 0;
}

// Header payload is small; accumulate the fixed 20 bytes in msgbuf, then the desc.
static int header_byte(vgacap_reader_t *r, uint8_t b) {
    uint32_t i = r->consumed;
    if (i < 20) { r->msgbuf[i] = (char)b; if (i == 19) {
        const uint8_t *p = (const uint8_t *)r->msgbuf;
        r->header.version = get_u16(p); if (r->header.version != 1) return fail(r, "unsupported version");
        r->header.sample_bits = p[2]; r->header.mode = p[3]; r->header.clock_hz = get_u32(p + 4);
        memcpy(r->header.signal_map, p + 8, VGACAP_SIG_COUNT);
        r->header.samples_per_word = p[16]; r->header.flags = p[17];
        uint16_t dl = get_u16(p + 18); if (dl != r->length - 20) return fail(r, "desc length mismatch");
        r->header.desc_len = (uint8_t)dl; r->header.desc[dl] = 0;
        if (!(r->header.sample_bits == 8 || r->header.sample_bits == 12 || r->header.sample_bits == 16 || r->header.sample_bits == 32)) return fail(r, "bad sample_bits");
        uint8_t spw = r->header.samples_per_word;
        if (!(spw == 1 || spw == 2 || spw == 4 || spw == 8) || spw * r->header.sample_bits > 32) return fail(r, "bad samples_per_word");
    } }
    else r->header.desc[i - 20] = (char)b;
    return 0;
}

static int payload_byte(vgacap_reader_t *r, uint8_t b) {
    if (tag_is(r, VGACAP_TAG_HEADER)) return header_byte(r, b);
    return 0; // skip unknown
}

int vgacap_reader_feed(vgacap_reader_t *r, const uint8_t *buf, size_t len) {
    for (size_t i = 0; i < len; i++) {
        if (!r->in_payload) {
            r->hdrbuf[r->hdrfill++] = buf[i];
            if (r->hdrfill == 8) {
                memcpy(r->tag, r->hdrbuf, 4); r->length = get_u32(r->hdrbuf + 4); r->in_payload = 1;
                if (begin_payload(r)) return -1;
                if (r->length == 0 && end_payload(r)) return -1;
            }
        } else {
            if (payload_byte(r, buf[i])) return -1;
            r->consumed++;
            if (r->consumed == r->length && end_payload(r)) return -1;
        }
    }
    return 0;
}
```

- [ ] **Step 4: Run tests**

Run: `cmake --build build && ctest --test-dir build --output-on-failure`
Expected: both header tests pass, smoke passes.

- [ ] **Step 5: Commit**

```bash
git add include/vgacap/stream.h src/stream tests/test_stream_header.c CMakeLists.txt
git commit -m "stream: VGCH header writer and incremental reader"
```

---

### Task 3: RAW chunks with word unpacking

**Files:**
- Modify: `include/vgacap/stream.h`, `src/stream/writer.c`, `src/stream/reader.c`
- Create: `tests/test_stream_raw.c`

**Interfaces:**
- Produces: `int vgacap_writer_raw(vgacap_writer_t *w, const uint32_t *words, uint32_t sample_count);` (words already packed per header; `ceil(sample_count/spw)` words are written) and `int vgacap_writer_raw_samples(vgacap_writer_t *w, const uint32_t *samples, uint32_t sample_count, uint32_t *wordbuf, size_t wordbuf_len);` (packs samples into `wordbuf` per header and writes; returns -1 if `wordbuf` too small). Reader emits `VGACAP_EV_RUN` with `run = 1` per sample, in order, value masked to `sample_bits`.

- [ ] **Step 1: Write the failing test**

`tests/test_stream_raw.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "harness.h"
#include "vgacap/stream.h"

static uint8_t outbuf[65536]; static size_t outlen;
static int capture_write(void *u, const uint8_t *b, size_t n) { (void)u; memcpy(outbuf + outlen, b, n); outlen += n; return 0; }
static uint32_t got[4096]; static size_t ngot;
static void on_event(void *u, const vgacap_event_t *ev) { (void)u;
    if (ev->type == VGACAP_EV_RUN) { for (uint32_t i = 0; i < ev->u.run.run; i++) got[ngot++] = ev->u.run.value; } }

static void roundtrip(uint8_t bits, uint8_t spw, uint8_t flags, uint32_t n) {
    vgacap_header_t h; vgacap_header_init_tinyvga(&h, bits, spw, flags);
    vgacap_writer_t w; outlen = 0; vgacap_writer_init(&w, capture_write, NULL, &h);
    uint32_t samples[1000], words[1000];
    uint32_t mask = bits == 32 ? 0xFFFFFFFFu : ((1u << bits) - 1u);
    for (uint32_t i = 0; i < n; i++) samples[i] = (i * 2654435761u) & mask;
    ASSERT_EQ_U(vgacap_writer_raw_samples(&w, samples, n, words, 1000), 0);
    vgacap_reader_t r; ngot = 0; vgacap_reader_init(&r, on_event, NULL);
    // feed in odd-sized pieces
    size_t pos = 0; while (pos < outlen) { size_t k = outlen - pos < 7 ? outlen - pos : 7; vgacap_reader_feed(&r, outbuf + pos, k); pos += k; }
    ASSERT_EQ_U(ngot, n);
    for (uint32_t i = 0; i < n; i++) ASSERT_EQ_U(got[i], samples[i]);
}

TEST(raw_8bit_4_per_word_lsb_first) { roundtrip(8, 4, 0, 1000); }
TEST(raw_8bit_4_per_word_msb_first) { roundtrip(8, 4, VGACAP_FLAG_FIRST_SAMPLE_MSB, 999); }
TEST(raw_12bit_2_per_word) { roundtrip(12, 2, 0, 501); }
TEST(raw_12bit_1_per_word) { roundtrip(12, 1, 0, 33); }
TEST(raw_16bit_2_per_word_msb) { roundtrip(16, 2, VGACAP_FLAG_FIRST_SAMPLE_MSB, 100); }
TEST(raw_32bit) { roundtrip(32, 1, 0, 64); }

TEST(raw_wire_layout_lsb_first) {
    vgacap_header_t h; vgacap_header_init_tinyvga(&h, 8, 4, 0);
    vgacap_writer_t w; outlen = 0; vgacap_writer_init(&w, capture_write, NULL, &h);
    uint32_t s[5] = { 0x11, 0x22, 0x33, 0x44, 0x55 }, words[2];
    size_t start = outlen;
    ASSERT_EQ_U(vgacap_writer_raw_samples(&w, s, 5, words, 2), 0);
    ASSERT_EQ_MEM(outbuf + start, "RAW ", 4);
    ASSERT_EQ_U(outbuf[start + 4], 4 + 8);              // length: count + 2 words
    ASSERT_EQ_U(outbuf[start + 8], 5);                  // sample_count
    const uint8_t expect[8] = { 0x11, 0x22, 0x33, 0x44, 0x55, 0, 0, 0 };
    ASSERT_EQ_MEM(outbuf + start + 12, expect, 8);
}

int main(void) { RUN(raw_8bit_4_per_word_lsb_first); RUN(raw_8bit_4_per_word_msb_first); RUN(raw_12bit_2_per_word);
    RUN(raw_12bit_1_per_word); RUN(raw_16bit_2_per_word_msb); RUN(raw_32bit); RUN(raw_wire_layout_lsb_first); RUN_TESTS_END(); }
```

- [ ] **Step 2: Run to verify it fails**

Add `vgacap_add_test(test_stream_raw)`. Run: `cmake --build build` → link errors for `vgacap_writer_raw_samples`.

- [ ] **Step 3: Implement**

Writer additions:

```c
static uint32_t sample_mask(uint8_t bits) { return bits == 32 ? 0xFFFFFFFFu : ((1u << bits) - 1u); }

int vgacap_writer_raw(vgacap_writer_t *w, const uint32_t *words, uint32_t sample_count) {
    uint32_t spw = w->header.samples_per_word, nwords = (sample_count + spw - 1) / spw;
    if (write_chunk_head(w, VGACAP_TAG_RAW, 4u + 4u * nwords)) return -1;
    uint8_t c[4]; put_u32(c, sample_count); if (w->write(w->user, c, 4)) return -1;
    for (uint32_t i = 0; i < nwords; i++) { put_u32(c, words[i]); if (w->write(w->user, c, 4)) return -1; }
    return 0;
}

uint32_t vgacap_pack_samples(const vgacap_header_t *h, const uint32_t *samples, uint32_t n, uint32_t *words) {
    uint32_t spw = h->samples_per_word, bits = h->sample_bits, mask = sample_mask(h->sample_bits);
    uint32_t nwords = (n + spw - 1) / spw;
    for (uint32_t i = 0; i < nwords; i++) words[i] = 0;
    for (uint32_t i = 0; i < n; i++) {
        uint32_t slot = i % spw; if (h->flags & VGACAP_FLAG_FIRST_SAMPLE_MSB) slot = spw - 1 - slot;
        uint32_t shift = slot * bits; words[i / spw] |= (samples[i] & mask) << shift;
    }
    return nwords;
}

int vgacap_writer_raw_samples(vgacap_writer_t *w, const uint32_t *samples, uint32_t n, uint32_t *wordbuf, size_t wordbuf_len) {
    uint32_t spw = w->header.samples_per_word; if ((n + spw - 1) / spw > wordbuf_len) return -1;
    vgacap_pack_samples(&w->header, samples, n, wordbuf);
    return vgacap_writer_raw(w, wordbuf, n);
}
```

Declare `vgacap_pack_samples` in the header too (the Python tests and later tools use it).

Reader additions. In `begin_payload`, for `RAW `: nothing extra (`sample_index` and `pfill` already reset). In `payload_byte`:

```c
static void emit_run(vgacap_reader_t *r, uint32_t value, uint32_t run) {
    vgacap_event_t ev; ev.type = VGACAP_EV_RUN; ev.u.run.value = value; ev.u.run.run = run; r->cb(r->user, &ev);
}

static void unpack_word(vgacap_reader_t *r, uint32_t word) {
    uint32_t spw = r->header.samples_per_word, bits = r->header.sample_bits, mask = sample_mask(bits);
    for (uint32_t s = 0; s < spw && r->sample_index < r->remaining_items; s++, r->sample_index++) {
        uint32_t slot = (r->header.flags & VGACAP_FLAG_FIRST_SAMPLE_MSB) ? spw - 1 - s : s;
        emit_run(r, (word >> (slot * bits)) & mask, 1);
    }
}

static int raw_byte(vgacap_reader_t *r, uint8_t b) {
    r->pbuf[r->pfill++] = b;
    if (r->consumed < 4) { if (r->pfill == 4) { r->remaining_items = get_u32(r->pbuf); r->pfill = 0; } return 0; }
    if (r->pfill == 4) { unpack_word(r, get_u32(r->pbuf)); r->pfill = 0; }
    return 0;
}
```

`consumed` is incremented by the caller after `payload_byte`, so inside `raw_byte` the count bytes are at `consumed` 0..3. Dispatch `RAW ` to `raw_byte` in `payload_byte`. `sample_mask` is duplicated in the reader (static).

- [ ] **Step 4: Run tests**

Run: `cmake --build build && ctest --test-dir build --output-on-failure`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add include/vgacap/stream.h src/stream tests/test_stream_raw.c CMakeLists.txt
git commit -m "stream: RAW chunks with per-header word packing"
```

---

### Task 4: RLE, FRAM, EVNT and TIME chunks

**Files:**
- Modify: `include/vgacap/stream.h`, `src/stream/writer.c`, `src/stream/reader.c`
- Create: `tests/test_stream_chunks.c`
- Modify (tracking repo): `docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md` — change "run length width fixed by the header" to "run lengths are u32".

**Interfaces:**
- Produces:

```c
int vgacap_writer_rle(vgacap_writer_t *w, const uint32_t *values, const uint32_t *runs, uint32_t pair_count);
int vgacap_writer_frame(vgacap_writer_t *w, uint32_t frame_counter, uint16_t first_line, uint16_t line_count,
                        uint32_t clocks_per_line, const uint32_t *words, uint32_t sample_count);
int vgacap_writer_events(vgacap_writer_t *w, const uint64_t *clocks, const uint32_t *values, uint32_t count);
int vgacap_writer_time(vgacap_writer_t *w, uint64_t host_time_ns, uint32_t clock_hz, uint32_t dropped, const char *msg);
```

Reader: `RLE ` emits one RUN per pair; `FRAM` emits `VGACAP_EV_FRAME_BEGIN` then RUNs (run=1) like RAW; `EVNT` emits, for each event after the first, a RUN of the previous value with `run = clock - prev_clock` (the final event's value is held in `last_event_value` and emitted as a 1-clock RUN when the chunk ends, so a stream of N events yields N runs whose total length is `last_clock - first_clock + 1`); `TIME` emits `VGACAP_EV_TIME` with `msg` pointing into `msgbuf` (valid during the callback).

- [ ] **Step 1: Write the failing test**

`tests/test_stream_chunks.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "harness.h"
#include "vgacap/stream.h"

static uint8_t outbuf[65536]; static size_t outlen;
static int capture_write(void *u, const uint8_t *b, size_t n) { (void)u; memcpy(outbuf + outlen, b, n); outlen += n; return 0; }
static vgacap_event_t evs[4096]; static char msgs[4096][64]; static size_t nev;
static void on_event(void *u, const vgacap_event_t *ev) { (void)u; evs[nev] = *ev;
    if (ev->type == VGACAP_EV_TIME) { memcpy(msgs[nev], ev->u.time.msg, ev->u.time.msg_len); msgs[nev][ev->u.time.msg_len] = 0; evs[nev].u.time.msg = msgs[nev]; }
    nev++; }
static void feed_all(void) { vgacap_reader_t r; nev = 0; vgacap_reader_init(&r, on_event, NULL);
    for (size_t i = 0; i < outlen; i++) vgacap_reader_feed(&r, outbuf + i, 1); }
static void start(uint8_t bits, uint8_t spw, vgacap_writer_t *w) { vgacap_header_t h; vgacap_header_init_tinyvga(&h, bits, spw, 0);
    outlen = 0; vgacap_writer_init(w, capture_write, NULL, &h); }

TEST(rle_roundtrip) {
    vgacap_writer_t w; start(8, 4, &w);
    uint32_t v[3] = { 0x88, 0x08, 0x3F }, n[3] = { 96, 48, 640 };
    ASSERT_EQ_U(vgacap_writer_rle(&w, v, n, 3), 0);
    feed_all();
    ASSERT_EQ_U(nev, 4); // header + 3 runs
    ASSERT_EQ_U(evs[1].type, VGACAP_EV_RUN); ASSERT_EQ_U(evs[1].u.run.value, 0x88); ASSERT_EQ_U(evs[1].u.run.run, 96);
    ASSERT_EQ_U(evs[3].u.run.value, 0x3F); ASSERT_EQ_U(evs[3].u.run.run, 640);
}

TEST(frame_roundtrip) {
    vgacap_writer_t w; start(8, 4, &w);
    uint32_t s[10] = { 1,2,3,4,5,6,7,8,9,10 }, words[3]; vgacap_pack_samples(&w.header, s, 10, words);
    ASSERT_EQ_U(vgacap_writer_frame(&w, 42, 100, 2, 5, words, 10), 0);
    feed_all();
    ASSERT_EQ_U(nev, 12);
    ASSERT_EQ_U(evs[1].type, VGACAP_EV_FRAME_BEGIN);
    ASSERT_EQ_U(evs[1].u.frame.frame_counter, 42); ASSERT_EQ_U(evs[1].u.frame.first_line, 100);
    ASSERT_EQ_U(evs[1].u.frame.line_count, 2); ASSERT_EQ_U(evs[1].u.frame.clocks_per_line, 5); ASSERT_EQ_U(evs[1].u.frame.sample_count, 10);
    for (int i = 0; i < 10; i++) { ASSERT_EQ_U(evs[2 + i].type, VGACAP_EV_RUN); ASSERT_EQ_U(evs[2 + i].u.run.value, (unsigned)(i + 1)); }
}

TEST(events_expand_to_runs) {
    vgacap_writer_t w; start(8, 1, &w);
    uint64_t c[4] = { 0, 10, 15, 100 }; uint32_t v[4] = { 0x80, 0x00, 0x80, 0x3F };
    ASSERT_EQ_U(vgacap_writer_events(&w, c, v, 4), 0);
    feed_all();
    ASSERT_EQ_U(nev, 5);
    ASSERT_EQ_U(evs[1].u.run.value, 0x80); ASSERT_EQ_U(evs[1].u.run.run, 10);
    ASSERT_EQ_U(evs[2].u.run.value, 0x00); ASSERT_EQ_U(evs[2].u.run.run, 5);
    ASSERT_EQ_U(evs[3].u.run.value, 0x80); ASSERT_EQ_U(evs[3].u.run.run, 85);
    ASSERT_EQ_U(evs[4].u.run.value, 0x3F); ASSERT_EQ_U(evs[4].u.run.run, 1);
}

TEST(time_roundtrip) {
    vgacap_writer_t w; start(8, 4, &w);
    ASSERT_EQ_U(vgacap_writer_time(&w, 1234567890123ull, 500000, 7, "fifo overrun"), 0);
    feed_all();
    ASSERT_EQ_U(nev, 2); ASSERT_EQ_U(evs[1].type, VGACAP_EV_TIME);
    ASSERT_EQ_U(evs[1].u.time.host_time_ns, 1234567890123ull); ASSERT_EQ_U(evs[1].u.time.clock_hz, 500000);
    ASSERT_EQ_U(evs[1].u.time.dropped_samples, 7); ASSERT_TRUE(strcmp(evs[1].u.time.msg, "fifo overrun") == 0);
}

TEST(unknown_chunk_is_skipped) {
    vgacap_writer_t w; start(8, 4, &w);
    const uint8_t junk[12] = { 'X','Y','Z','W', 4,0,0,0, 1,2,3,4 }; capture_write(NULL, junk, 12);
    uint32_t v = 5, n = 2; vgacap_writer_rle(&w, &v, &n, 1);
    feed_all();
    ASSERT_EQ_U(nev, 2); ASSERT_EQ_U(evs[1].u.run.run, 2);
}

int main(void) { RUN(rle_roundtrip); RUN(frame_roundtrip); RUN(events_expand_to_runs); RUN(time_roundtrip); RUN(unknown_chunk_is_skipped); RUN_TESTS_END(); }
```

- [ ] **Step 2: Run to verify it fails**

Add `vgacap_add_test(test_stream_chunks)`. Run: `cmake --build build` → link errors for the four writer functions.

- [ ] **Step 3: Implement**

Writer:

```c
int vgacap_writer_rle(vgacap_writer_t *w, const uint32_t *values, const uint32_t *runs, uint32_t pair_count) {
    if (write_chunk_head(w, VGACAP_TAG_RLE, 4u + 8u * pair_count)) return -1;
    uint8_t c[8]; put_u32(c, pair_count); if (w->write(w->user, c, 4)) return -1;
    for (uint32_t i = 0; i < pair_count; i++) { put_u32(c, values[i]); put_u32(c + 4, runs[i]); if (w->write(w->user, c, 8)) return -1; }
    return 0;
}

int vgacap_writer_frame(vgacap_writer_t *w, uint32_t frame_counter, uint16_t first_line, uint16_t line_count,
                        uint32_t clocks_per_line, const uint32_t *words, uint32_t sample_count) {
    uint32_t spw = w->header.samples_per_word, nwords = (sample_count + spw - 1) / spw;
    if (write_chunk_head(w, VGACAP_TAG_FRAME, 16u + 4u * nwords)) return -1;
    uint8_t c[16]; put_u32(c, frame_counter); put_u16(c + 4, first_line); put_u16(c + 6, line_count);
    put_u32(c + 8, clocks_per_line); put_u32(c + 12, sample_count);
    if (w->write(w->user, c, 16)) return -1;
    for (uint32_t i = 0; i < nwords; i++) { put_u32(c, words[i]); if (w->write(w->user, c, 4)) return -1; }
    return 0;
}

static void put_u64(uint8_t *p, uint64_t v) { put_u32(p, (uint32_t)v); put_u32(p + 4, (uint32_t)(v >> 32)); }

int vgacap_writer_events(vgacap_writer_t *w, const uint64_t *clocks, const uint32_t *values, uint32_t count) {
    if (write_chunk_head(w, VGACAP_TAG_EVENT, 4u + 12u * count)) return -1;
    uint8_t c[12]; put_u32(c, count); if (w->write(w->user, c, 4)) return -1;
    for (uint32_t i = 0; i < count; i++) { put_u64(c, clocks[i]); put_u32(c + 8, values[i]); if (w->write(w->user, c, 12)) return -1; }
    return 0;
}

int vgacap_writer_time(vgacap_writer_t *w, uint64_t host_time_ns, uint32_t clock_hz, uint32_t dropped, const char *msg) {
    size_t ml = msg ? strlen(msg) : 0; if (ml > 255) ml = 255;
    if (write_chunk_head(w, VGACAP_TAG_TIME, (uint32_t)(18 + ml))) return -1;
    uint8_t c[18]; put_u64(c, host_time_ns); put_u32(c + 8, clock_hz); put_u32(c + 12, dropped); put_u16(c + 16, (uint16_t)ml);
    if (w->write(w->user, c, 18)) return -1;
    if (ml && w->write(w->user, (const uint8_t *)msg, ml)) return -1;
    return 0;
}
```

Reader: extend `payload_byte` with `rle_byte`, `frame_byte`, `event_byte`, `time_byte`, each accumulating fixed-size records in `pbuf` the way `raw_byte` does:

```c
static int rle_byte(vgacap_reader_t *r, uint8_t b) {
    r->pbuf[r->pfill++] = b;
    if (r->consumed < 4) { if (r->pfill == 4) { r->remaining_items = get_u32(r->pbuf); r->pfill = 0; } return 0; }
    if (r->pfill == 8) { emit_run(r, get_u32(r->pbuf), get_u32(r->pbuf + 4)); r->pfill = 0; }
    return 0;
}

static int frame_byte(vgacap_reader_t *r, uint8_t b) {
    r->pbuf[r->pfill++] = b;
    if (r->consumed < 16) { if (r->pfill == 16) {
        vgacap_event_t ev; ev.type = VGACAP_EV_FRAME_BEGIN;
        ev.u.frame.frame_counter = get_u32(r->pbuf); ev.u.frame.first_line = get_u16(r->pbuf + 4);
        ev.u.frame.line_count = get_u16(r->pbuf + 6); ev.u.frame.clocks_per_line = get_u32(r->pbuf + 8);
        ev.u.frame.sample_count = get_u32(r->pbuf + 12); r->remaining_items = ev.u.frame.sample_count;
        r->cb(r->user, &ev); r->pfill = 0; } return 0; }
    if (r->pfill == 4) { unpack_word(r, get_u32(r->pbuf)); r->pfill = 0; }
    return 0;
}

static uint64_t get_u64(const uint8_t *p) { return (uint64_t)get_u32(p) | ((uint64_t)get_u32(p + 4) << 32); }

static int event_byte(vgacap_reader_t *r, uint8_t b) {
    r->pbuf[r->pfill++] = b;
    if (r->consumed < 4) { if (r->pfill == 4) { r->remaining_items = get_u32(r->pbuf); r->pfill = 0; r->have_last_event = 0; } return 0; }
    if (r->pfill == 12) {
        uint64_t clk = get_u64(r->pbuf); uint32_t val = get_u32(r->pbuf + 8); r->pfill = 0;
        if (r->have_last_event) { if (clk <= r->last_event_clock) return fail(r, "event clock not increasing");
            emit_run(r, r->last_event_value, (uint32_t)(clk - r->last_event_clock)); }
        r->last_event_clock = clk; r->last_event_value = val; r->have_last_event = 1;
    }
    return 0;
}

static int time_byte(vgacap_reader_t *r, uint8_t b) {
    if (r->consumed < 18) { r->pbuf[r->consumed] = b; return 0; }
    uint32_t mi = r->consumed - 18; if (mi < sizeof r->msgbuf - 1) r->msgbuf[mi] = (char)b; return 0;
}
```

In `end_payload`: for `EVNT` with `have_last_event`, `emit_run(r, r->last_event_value, 1)`; for `TIME`, build the `VGACAP_EV_TIME` event from `pbuf` (`host_time_ns = get_u64(pbuf)`, `clock_hz = get_u32(pbuf+8)`, `dropped = get_u32(pbuf+12)`, `msg_len = min(get_u16(pbuf+16), 255)`), NUL-terminate `msgbuf`, and call back. In `begin_payload`, validate lengths: `RLE ` `length >= 4`, `FRAM` `length >= 16`, `EVNT` `length >= 4`, `TIME` `length >= 18`; otherwise `fail`.

- [ ] **Step 4: Run tests**

Run: `cmake --build build && ctest --test-dir build --output-on-failure`
Expected: all pass.

- [ ] **Step 5: Commit (and the spec touch-up in the tracking repo)**

```bash
git add include/vgacap/stream.h src/stream tests/test_stream_chunks.c CMakeLists.txt
git commit -m "stream: RLE, FRAM, EVNT and TIME chunks"
cd ~/github/TinyTapeout/tt-vga-capture && sed -i 's/(value, run length) pairs; run length width fixed by the header./(u32 value, u32 run length) pairs./' docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md && git commit -am "spec: RLE run lengths are u32" && git push
```

---

### Task 5: Python mirror of the stream format, cross-checked against C with `vgacap-dump`

**Files:**
- Create: `python/vgacap/stream.py`, `python/tests/test_stream.py`, `src/tools/vgacap_dump.c`, `python/tests/test_roundtrip_c.py`
- Modify: `CMakeLists.txt` (add `vgacap-dump` executable)

**Interfaces:**
- Produces (Python):

```python
TINYVGA_MAP = (7, 3, 0, 4, 1, 5, 2, 6)
@dataclass
class Header: version: int = 1; sample_bits: int = 8; mode: int = 3; clock_hz: int = 0; signal_map: tuple = TINYVGA_MAP; samples_per_word: int = 4; flags: int = 0; desc: str = ""
class Writer:  # writes to a binary file object
    def __init__(self, fp, header: Header) -> None
    def raw(self, samples: Sequence[int]) -> None
    def rle(self, pairs: Sequence[tuple[int, int]]) -> None
    def frame(self, frame_counter: int, first_line: int, line_count: int, clocks_per_line: int, samples: Sequence[int]) -> None
    def events(self, events: Sequence[tuple[int, int]]) -> None
    def time(self, host_time_ns: int, clock_hz: int, dropped: int, msg: str) -> None
def pack_words(header: Header, samples) -> list[int]
def unpack_words(header: Header, words, count) -> list[int]
def read_chunks(data: bytes) -> Iterator[tuple[str, bytes]]
def read_stream(data: bytes) -> tuple[Header, list]   # list of ("run", value, run) | ("frame", fc, first_line, line_count, cpl, n) | ("time", ...)
```

- Produces (C CLI): `vgacap-dump <file>` prints one line per chunk: `VGCH bits=12 spw=2 flags=0 clock=25175000 map=7,3,0,4,1,5,2,6 desc="..."`, `RAW  samples=N`, `RLE  pairs=N runs=TOTAL`, `FRAM counter=C first=L lines=N cpl=X samples=N`, `EVNT events=N`, `TIME t=NS clock=HZ dropped=D msg="..."`; then a final line `total_samples=T crc32=HEX` where the CRC is over the sequence of emitted sample values expanded from runs (one byte per sample, value & 0xFF, then value >> 8 & 0xFF for widths above 8... use a simple running FNV-1a 32-bit over the 4 little-endian bytes of each expanded sample; print as 8 hex digits). Exit 1 on reader error.

- [ ] **Step 1: Write the failing Python tests**

`python/tests/test_stream.py`:

```python
import io
from vgacap.stream import Header, Writer, pack_words, unpack_words, read_chunks, read_stream, TINYVGA_MAP

def test_pack_lsb_first():
    h = Header(sample_bits=8, samples_per_word=4)
    assert pack_words(h, [0x11, 0x22, 0x33, 0x44, 0x55]) == [0x44332211, 0x00000055]

def test_pack_msb_first_12bit():
    h = Header(sample_bits=12, samples_per_word=2, flags=1)
    assert pack_words(h, [0xABC, 0x123]) == [0xABC00000 >> 8 | 0x123]  # 0xABC123
    assert unpack_words(h, [0xABC123], 2) == [0xABC, 0x123]

def test_header_bytes():
    fp = io.BytesIO(); Writer(fp, Header(sample_bits=12, samples_per_word=2, clock_hz=25175000, desc="x"))
    data = fp.getvalue()
    assert data[:4] == b"VGCH" and data[4] == 21 and data[8:10] == b"\x01\x00" and data[10] == 12
    assert data[16:24] == bytes(TINYVGA_MAP) and data[24] == 2 and data[26:28] == b"\x01\x00" and data[28:29] == b"x"

def test_roundtrip_all_chunks():
    fp = io.BytesIO(); w = Writer(fp, Header(sample_bits=8, samples_per_word=4))
    w.raw([1, 2, 3, 4, 5]); w.rle([(0x88, 96), (0x3F, 640)]); w.frame(7, 10, 1, 5, [9, 8, 7, 6, 5])
    w.events([(0, 0x80), (10, 0x00), (12, 0x3F)]); w.time(123, 500000, 0, "ok")
    header, items = read_stream(fp.getvalue())
    assert header.sample_bits == 8
    runs = [i for i in items if i[0] == "run"]
    assert runs[:5] == [("run", v, 1) for v in (1, 2, 3, 4, 5)]
    assert ("run", 0x88, 96) in runs and ("run", 0x3F, 640) in runs
    assert ("frame", 7, 10, 1, 5, 5) in items
    assert runs[-3:] == [("run", 0x80, 10), ("run", 0x00, 2), ("run", 0x3F, 1)]
    assert [i for i in items if i[0] == "time"] == [("time", 123, 500000, 0, "ok")]
    assert [t for t, _ in read_chunks(fp.getvalue())] == ["VGCH", "RAW ", "RLE ", "FRAM", "EVNT", "TIME"]
```

`python/tests/test_roundtrip_c.py`:

```python
import io, subprocess, pathlib, random
from vgacap.stream import Header, Writer

DUMP = pathlib.Path(__file__).resolve().parents[2] / "build" / "vgacap-dump"

def fnv1a(samples):
    h = 0x811C9DC5
    for s in samples:
        for b in s.to_bytes(4, "little"):
            h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h

def test_c_dump_agrees_with_python(tmp_path):
    rng = random.Random(1)
    samples = [rng.randrange(4096) for _ in range(1001)]
    fp = io.BytesIO(); w = Writer(fp, Header(sample_bits=12, samples_per_word=2, flags=1, clock_hz=25000000, desc="py"))
    w.raw(samples); w.rle([(0x800, 100)]); w.events([(0, 0x1), (5, 0x2)])
    f = tmp_path / "s.vgacap"; f.write_bytes(fp.getvalue())
    out = subprocess.run([str(DUMP), str(f)], capture_output=True, text=True, check=True).stdout
    expanded = samples + [0x800] * 100 + [0x1] * 5 + [0x2]
    assert f"total_samples={len(expanded)} crc32={fnv1a(expanded):08x}" in out
    assert "VGCH bits=12 spw=2 flags=1 clock=25000000" in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest -q` → `ModuleNotFoundError: vgacap.stream`.

- [ ] **Step 3: Implement `python/vgacap/stream.py`**

```python
# SPDX-License-Identifier: Apache-2.0
"""Mirror of the vgacap stream format (see include/vgacap/stream.h)."""
from __future__ import annotations
import struct
from dataclasses import dataclass
from typing import Iterator, Sequence

TINYVGA_MAP = (7, 3, 0, 4, 1, 5, 2, 6)
FLAG_FIRST_SAMPLE_MSB = 1

@dataclass
class Header:
    version: int = 1
    sample_bits: int = 8
    mode: int = 3
    clock_hz: int = 0
    signal_map: tuple = TINYVGA_MAP
    samples_per_word: int = 4
    flags: int = 0
    desc: str = ""

    def mask(self) -> int:
        return (1 << self.sample_bits) - 1

def _slot(h: Header, i: int) -> int:
    s = i % h.samples_per_word
    return h.samples_per_word - 1 - s if h.flags & FLAG_FIRST_SAMPLE_MSB else s

def pack_words(h: Header, samples: Sequence[int]) -> list[int]:
    spw = h.samples_per_word
    words = [0] * ((len(samples) + spw - 1) // spw)
    for i, s in enumerate(samples):
        words[i // spw] |= (s & h.mask()) << (_slot(h, i) * h.sample_bits)
    return words

def unpack_words(h: Header, words: Sequence[int], count: int) -> list[int]:
    return [(words[i // h.samples_per_word] >> (_slot(h, i) * h.sample_bits)) & h.mask() for i in range(count)]

def _chunk(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<I", len(payload)) + payload

class Writer:
    def __init__(self, fp, header: Header) -> None:
        self.fp, self.h = fp, header
        desc = header.desc.encode()
        body = struct.pack("<HBBI8sBBH", header.version, header.sample_bits, header.mode, header.clock_hz,
                           bytes(header.signal_map), header.samples_per_word, header.flags, len(desc)) + desc
        fp.write(_chunk(b"VGCH", body))

    def _words(self, samples) -> bytes:
        return b"".join(struct.pack("<I", w) for w in pack_words(self.h, samples))

    def raw(self, samples: Sequence[int]) -> None:
        self.fp.write(_chunk(b"RAW ", struct.pack("<I", len(samples)) + self._words(samples)))

    def rle(self, pairs: Sequence[tuple[int, int]]) -> None:
        self.fp.write(_chunk(b"RLE ", struct.pack("<I", len(pairs)) + b"".join(struct.pack("<II", v, r) for v, r in pairs)))

    def frame(self, frame_counter: int, first_line: int, line_count: int, clocks_per_line: int, samples: Sequence[int]) -> None:
        head = struct.pack("<IHHII", frame_counter, first_line, line_count, clocks_per_line, len(samples))
        self.fp.write(_chunk(b"FRAM", head + self._words(samples)))

    def events(self, events: Sequence[tuple[int, int]]) -> None:
        self.fp.write(_chunk(b"EVNT", struct.pack("<I", len(events)) + b"".join(struct.pack("<QI", c, v) for c, v in events)))

    def time(self, host_time_ns: int, clock_hz: int, dropped: int, msg: str) -> None:
        m = msg.encode()[:255]
        self.fp.write(_chunk(b"TIME", struct.pack("<QIIH", host_time_ns, clock_hz, dropped, len(m)) + m))

def read_chunks(data: bytes) -> Iterator[tuple[str, bytes]]:
    pos = 0
    while pos + 8 <= len(data):
        tag, length = data[pos:pos + 4].decode("ascii"), struct.unpack_from("<I", data, pos + 4)[0]
        pos += 8
        if pos + length > len(data):
            raise ValueError(f"truncated chunk {tag!r}")
        yield tag, data[pos:pos + length]
        pos += length

def parse_header(payload: bytes) -> Header:
    version, bits, mode, clock, smap, spw, flags, dl = struct.unpack_from("<HBBI8sBBH", payload, 0)
    if version != 1:
        raise ValueError(f"unsupported version {version}")
    return Header(version, bits, mode, clock, tuple(smap), spw, flags, payload[20:20 + dl].decode())

def read_stream(data: bytes) -> tuple[Header, list]:
    header, items = None, []
    for tag, p in read_chunks(data):
        if tag == "VGCH":
            header = parse_header(p); continue
        if header is None:
            raise ValueError("chunk before header")
        if tag in ("RAW ", "FRAM"):
            off = 4 if tag == "RAW " else 16
            if tag == "FRAM":
                fc, fl, lc, cpl, n = struct.unpack_from("<IHHII", p, 0); items.append(("frame", fc, fl, lc, cpl, n))
            else:
                n = struct.unpack_from("<I", p, 0)[0]
            words = struct.unpack_from(f"<{(len(p) - off) // 4}I", p, off)
            items.extend(("run", v, 1) for v in unpack_words(header, words, n))
        elif tag == "RLE ":
            n = struct.unpack_from("<I", p, 0)[0]
            items.extend(("run", v, r) for v, r in struct.iter_unpack("<II", p[4:4 + 8 * n]))
        elif tag == "EVNT":
            n = struct.unpack_from("<I", p, 0)[0]
            evs = list(struct.iter_unpack("<QI", p[4:4 + 12 * n]))
            for (c0, v0), (c1, _) in zip(evs, evs[1:]):
                if c1 <= c0:
                    raise ValueError("event clock not increasing")
                items.append(("run", v0, c1 - c0))
            if evs:
                items.append(("run", evs[-1][1], 1))
        elif tag == "TIME":
            t, clk, dropped, ml = struct.unpack_from("<QIIH", p, 0)
            items.append(("time", t, clk, dropped, p[18:18 + ml].decode(errors="replace")))
    if header is None:
        raise ValueError("no header")
    return header, items
```

`src/tools/vgacap_dump.c`: open the file, read in 64 KiB blocks, feed the reader; the callback prints the lines described under Interfaces, keeps `total_samples` and the FNV-1a hash (`h = (h ^ byte) * 16777619u` over the four little-endian bytes of each sample, repeated `run` times: for large runs iterate the four-byte update `run` times; correctness over speed here). On `VGACAP_EV_ERROR` print `error: <what>` to stderr and exit 1. For per-chunk lines, count RUN events per chunk by tracking the reader's `tag` between events: simplest is to print chunk lines from a second pass over the file with a tiny local chunk walker (tag + length only) before the reader pass; the reader pass prints only the final line. Add to `CMakeLists.txt`: `add_executable(vgacap-dump src/tools/vgacap_dump.c)` + `target_link_libraries(vgacap-dump PRIVATE vgacap_stream)`.

- [ ] **Step 4: Run tests**

Run: `cmake --build build && ctest --test-dir build --output-on-failure && uv run pytest -q`
Expected: all pass, including the C/Python cross-check.

- [ ] **Step 5: Commit**

```bash
git add python/vgacap/stream.py python/tests/test_stream.py && git commit -m "python: stream format writer and reader"
git add src/tools/vgacap_dump.c CMakeLists.txt python/tests/test_roundtrip_c.py && git commit -m "tools: vgacap-dump and C/Python cross-check"
```

---

### Task 6: Mode table and sync timing learning

**Files:**
- Create: `include/vgacap/frame.h`, `src/frame/modes.c`, `src/frame/timing.c`, `tests/test_modes.c`, `tests/test_timing.c`, `tests/synth.h`, `tests/synth.c`
- Modify: `CMakeLists.txt` (add `vgacap_frame` static library: `src/frame/modes.c src/frame/timing.c`; tests link both libraries; `synth.c` compiled into the frame tests)

**Interfaces:**
- Produces (`include/vgacap/frame.h`, part 1):

```c
typedef struct vgaframe_mode {
    const char *name;
    uint16_t h_active, h_front, h_sync, h_back;   // clocks
    uint16_t v_active, v_front, v_sync, v_back;   // lines
    uint8_t  h_sync_positive, v_sync_positive;    // 1 = pulse is high
} vgaframe_mode_t;
// clocks per line = h_active+h_front+h_sync+h_back; lines per frame likewise.
const vgaframe_mode_t *vgaframe_modes(size_t *count);
// exact match on clocks_per_line and lines_per_frame; NULL if none
const vgaframe_mode_t *vgaframe_mode_match(uint32_t clocks_per_line, uint32_t lines_per_frame);

typedef struct vgaframe_timing {
    uint32_t clocks_per_line, lines_per_frame;
    uint32_t hsync_width;        // clocks
    uint32_t vsync_lines;        // lines
    uint8_t  hsync_positive, vsync_positive;
    uint8_t  locked;             // 1 once two consecutive frames agree
    const vgaframe_mode_t *mode; // matched entry or NULL
} vgaframe_timing_t;

// Internal learner used by vgaframe; exposed for tests.
typedef struct vgaframe_timing_learner {
    vgaframe_timing_t t;
    uint8_t  prev_h, prev_v, have_prev;
    uint32_t clk_in_line;        // clocks since the last hsync leading edge (rising or falling, whichever came first)
    uint32_t h_high, h_low;      // duration of the current/previous hsync phases
    uint32_t line_in_frame;
    uint32_t v_high_lines, v_low_lines;
    uint32_t last_cpl, last_lpf; // previous measurements for the lock check
    uint32_t h_edge_count;
} vgaframe_timing_learner_t;

void vgaframe_timing_init(vgaframe_timing_learner_t *l);
// feed one sample's sync levels for `run` clocks; returns 1 when a new line started, 2 when a new frame started, else 0
int  vgaframe_timing_push(vgaframe_timing_learner_t *l, uint8_t hsync, uint8_t vsync, uint32_t run);
```

Built-in mode table (all timings from the VESA/industry-standard values):

| name | h_active | h_front | h_sync | h_back | v_active | v_front | v_sync | v_back | h+ | v+ |
|---|---|---|---|---|---|---|---|---|---|---|
| 640x480@60 | 640 | 16 | 96 | 48 | 480 | 10 | 2 | 33 | 0 | 0 |
| 640x480@72 | 640 | 24 | 40 | 128 | 480 | 9 | 3 | 28 | 0 | 0 |
| 640x480@75 | 640 | 16 | 64 | 120 | 480 | 1 | 3 | 16 | 0 | 0 |
| 720x400@70 | 720 | 18 | 108 | 54 | 400 | 12 | 2 | 35 | 0 | 1 |
| 800x600@56 | 800 | 24 | 72 | 128 | 600 | 1 | 2 | 22 | 1 | 1 |
| 800x600@60 | 800 | 40 | 128 | 88 | 600 | 1 | 4 | 23 | 1 | 1 |
| 1024x768@60 | 1024 | 24 | 136 | 160 | 768 | 3 | 6 | 29 | 0 | 0 |

- Produces (`tests/synth.h`): `size_t synth_frame(const vgaframe_mode_t *m, uint8_t (*pixel)(void *user, uint16_t x, uint16_t y), void *user, uint32_t *out, size_t out_len);` writes one full frame of 8-bit Tiny VGA samples (`hsync` bit 7, `vsync` bit 3, colour in bits 0,1,2,4,5,6 per the Tiny VGA map; `pixel` returns 6-bit colour as `rr gg bb` = bits 5..0), starting at the leading edge of the vsync pulse's first line's hsync pulse; returns the sample count (`cpl * lpf`) or 0 if `out_len` too small. Sync polarity from the mode. Colour is 0 outside the active area.

Timing learner algorithm (`timing.c`):
1. Track hsync edges. Each hsync edge ends a phase; record its duration. After both a high and a low phase are known, the **shorter** phase is the pulse: `hsync_positive = (h_high < h_low)`. The leading edge of the pulse (the transition *into* the pulse level) is the line start: set `clk_in_line = 0`, `clocks_per_line = length of the completed line`, `hsync_width = pulse duration`, return 1.
2. Sample vsync once per line at the line start. Count consecutive lines at each level; when vsync changes, the shorter phase is the pulse: `vsync_positive` likewise. The line where vsync enters its pulse level is line 0: `lines_per_frame = line_in_frame`, `vsync_lines = pulse length in lines`, return 2.
3. `locked = 1` when the newly measured `clocks_per_line` and `lines_per_frame` equal the previous frame's values; `mode = vgaframe_mode_match(...)` each frame.
4. Runs: `vgaframe_timing_push(l, h, v, run)` advances `clk_in_line += run` and phase durations by `run`; edges only occur *between* pushes (a push is a constant level), so a run never contains an edge.

- [ ] **Step 1: Write the failing tests**

`tests/test_modes.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "harness.h"
#include "vgacap/frame.h"
TEST(table_has_640x480) { size_t n; const vgaframe_mode_t *m = vgaframe_modes(&n); ASSERT_TRUE(n >= 7); ASSERT_TRUE(strcmp(m[0].name, "640x480@60") == 0); }
TEST(match_640x480) { const vgaframe_mode_t *m = vgaframe_mode_match(800, 525); ASSERT_TRUE(m != NULL); ASSERT_EQ_U(m->h_active, 640); ASSERT_EQ_U(m->v_back, 33); }
TEST(match_800x600) { const vgaframe_mode_t *m = vgaframe_mode_match(1056, 628); ASSERT_TRUE(m != NULL); ASSERT_EQ_U(m->h_sync_positive, 1); }
TEST(no_match) { ASSERT_TRUE(vgaframe_mode_match(801, 525) == NULL); }
int main(void) { RUN(table_has_640x480); RUN(match_640x480); RUN(match_800x600); RUN(no_match); RUN_TESTS_END(); }
```

`tests/test_timing.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "harness.h"
#include "vgacap/frame.h"
#include "synth.h"

static uint32_t buf[1400 * 900];
static uint8_t black(void *u, uint16_t x, uint16_t y) { (void)u; (void)x; (void)y; return 0; }

static void learn(const vgaframe_mode_t *m, vgaframe_timing_learner_t *l, int frames) {
    size_t n = synth_frame(m, black, NULL, buf, sizeof buf / sizeof buf[0]);
    ASSERT_TRUE(n > 0);
    vgaframe_timing_init(l);
    for (int f = 0; f < frames; f++)
        for (size_t i = 0; i < n; i++) vgaframe_timing_push(l, (buf[i] >> 7) & 1, (buf[i] >> 3) & 1, 1);
}

TEST(learns_640x480_negative_syncs) {
    vgaframe_timing_learner_t l; learn(vgaframe_mode_match(800, 525), &l, 3);
    ASSERT_EQ_U(l.t.clocks_per_line, 800); ASSERT_EQ_U(l.t.lines_per_frame, 525);
    ASSERT_EQ_U(l.t.hsync_width, 96); ASSERT_EQ_U(l.t.vsync_lines, 2);
    ASSERT_EQ_U(l.t.hsync_positive, 0); ASSERT_EQ_U(l.t.vsync_positive, 0);
    ASSERT_EQ_U(l.t.locked, 1); ASSERT_TRUE(l.t.mode != NULL); ASSERT_TRUE(strcmp(l.t.mode->name, "640x480@60") == 0);
}

TEST(learns_800x600_positive_syncs) {
    vgaframe_timing_learner_t l; learn(vgaframe_mode_match(1056, 628), &l, 3);
    ASSERT_EQ_U(l.t.clocks_per_line, 1056); ASSERT_EQ_U(l.t.lines_per_frame, 628);
    ASSERT_EQ_U(l.t.hsync_positive, 1); ASSERT_EQ_U(l.t.vsync_positive, 1); ASSERT_EQ_U(l.t.locked, 1);
}

TEST(runs_are_equivalent_to_samples) {
    const vgaframe_mode_t *m = vgaframe_mode_match(800, 525);
    size_t n = synth_frame(m, black, NULL, buf, sizeof buf / sizeof buf[0]);
    vgaframe_timing_learner_t l; vgaframe_timing_init(&l);
    for (int f = 0; f < 3; f++) { size_t i = 0; while (i < n) { size_t j = i; while (j < n && buf[j] == buf[i]) j++;
        vgaframe_timing_push(&l, (buf[i] >> 7) & 1, (buf[i] >> 3) & 1, (uint32_t)(j - i)); i = j; } }
    ASSERT_EQ_U(l.t.clocks_per_line, 800); ASSERT_EQ_U(l.t.lines_per_frame, 525); ASSERT_EQ_U(l.t.locked, 1);
}

TEST(reports_line_and_frame_starts) {
    const vgaframe_mode_t *m = vgaframe_mode_match(800, 525);
    size_t n = synth_frame(m, black, NULL, buf, sizeof buf / sizeof buf[0]);
    vgaframe_timing_learner_t l; vgaframe_timing_init(&l); int lines = 0, frames = 0;
    for (int f = 0; f < 3; f++) for (size_t i = 0; i < n; i++) { int r = vgaframe_timing_push(&l, (buf[i] >> 7) & 1, (buf[i] >> 3) & 1, 1);
        if (r == 1) lines++; if (r == 2) frames++; }
    ASSERT_TRUE(frames >= 2); ASSERT_TRUE(lines >= 2 * 525);
}

int main(void) { RUN(learns_640x480_negative_syncs); RUN(learns_800x600_positive_syncs); RUN(runs_are_equivalent_to_samples); RUN(reports_line_and_frame_starts); RUN_TESTS_END(); }
```

`tests/synth.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "synth.h"
size_t synth_frame(const vgaframe_mode_t *m, uint8_t (*pixel)(void *, uint16_t, uint16_t), void *user, uint32_t *out, size_t out_len) {
    uint32_t cpl = (uint32_t)m->h_active + m->h_front + m->h_sync + m->h_back;
    uint32_t lpf = (uint32_t)m->v_active + m->v_front + m->v_sync + m->v_back;
    if ((size_t)cpl * lpf > out_len) return 0;
    size_t k = 0;
    for (uint32_t line = 0; line < lpf; line++) {
        // line 0 starts at the vsync pulse; active lines follow v_sync + v_back
        int v_pulse = line < m->v_sync;
        int y_active = line >= (uint32_t)m->v_sync + m->v_back && line < (uint32_t)m->v_sync + m->v_back + m->v_active;
        uint16_t y = (uint16_t)(line - m->v_sync - m->v_back);
        for (uint32_t clk = 0; clk < cpl; clk++) {
            int h_pulse = clk < m->h_sync;
            int x_active = clk >= (uint32_t)m->h_sync + m->h_back && clk < (uint32_t)m->h_sync + m->h_back + m->h_active;
            uint16_t x = (uint16_t)(clk - m->h_sync - m->h_back);
            uint8_t hs = (uint8_t)(m->h_sync_positive ? h_pulse : !h_pulse);
            uint8_t vs = (uint8_t)(m->v_sync_positive ? v_pulse : !v_pulse);
            uint8_t c = (x_active && y_active) ? pixel(user, x, y) : 0;   // c = rr gg bb
            uint8_t r1 = (c >> 5) & 1, r0 = (c >> 4) & 1, g1 = (c >> 3) & 1, g0 = (c >> 2) & 1, b1 = (c >> 1) & 1, b0 = c & 1;
            out[k++] = (uint32_t)((hs << 7) | (b0 << 6) | (g0 << 5) | (r0 << 4) | (vs << 3) | (b1 << 2) | (g1 << 1) | r1);
        }
    }
    return k;
}
```

- [ ] **Step 2: Run to verify it fails**

Add to CMake: `add_library(vgacap_frame STATIC src/frame/modes.c src/frame/timing.c)`, link tests to both libraries, `vgacap_add_test(test_modes)`, `vgacap_add_test(test_timing tests/synth.c)`. Create `include/vgacap/frame.h` with the declarations above and empty `.c` files. Run: `cmake -S . -B build && cmake --build build` → link errors.

- [ ] **Step 3: Implement `modes.c` and `timing.c`**

`modes.c`: the table above as a `static const vgaframe_mode_t table[]`, `vgaframe_modes` returns it, `vgaframe_mode_match` loops computing `cpl`/`lpf`.

`timing.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "vgacap/frame.h"
#include <string.h>

void vgaframe_timing_init(vgaframe_timing_learner_t *l) { memset(l, 0, sizeof *l); }

static void line_start(vgaframe_timing_learner_t *l, uint8_t v, int *ret) {
    // completed line length
    if (l->h_edge_count >= 2) { l->t.clocks_per_line = l->clk_in_line; }
    l->clk_in_line = 0; l->line_in_frame++; *ret = 1;
    // vsync sampled once per line
    if (l->have_prev) {
        if (v == l->prev_v) { if (v) l->v_high_lines++; else l->v_low_lines++; }
        else {
            uint32_t ended = l->prev_v ? l->v_high_lines : l->v_low_lines;
            uint32_t other = l->prev_v ? l->v_low_lines : l->v_high_lines;
            if (other) { // both phases seen: the shorter one is the pulse
                uint8_t ended_is_pulse = ended < other;
                if (ended_is_pulse) { /* leaving the pulse: nothing */ }
                else { // entering the pulse => frame start
                    l->t.vsync_positive = v; l->t.vsync_lines = 0;
                    l->t.lines_per_frame = l->line_in_frame - 1; // lines since previous frame start
                    l->t.locked = (l->t.lines_per_frame == l->last_lpf && l->t.clocks_per_line == l->last_cpl && l->last_lpf != 0);
                    l->last_lpf = l->t.lines_per_frame; l->last_cpl = l->t.clocks_per_line;
                    l->t.mode = vgaframe_mode_match(l->t.clocks_per_line, l->t.lines_per_frame);
                    l->line_in_frame = 1; *ret = 2;
                }
            }
            if (v) { l->v_high_lines = 1; } else { l->v_low_lines = 1; }
            if (l->t.vsync_positive == v && *ret == 2) l->t.vsync_lines = 1;
        }
        if (*ret != 2 && l->t.vsync_positive == v && l->t.lines_per_frame && v == l->prev_v && l->line_in_frame <= l->t.vsync_lines + 1) l->t.vsync_lines++;
    }
    l->prev_v = v;
}

int vgaframe_timing_push(vgaframe_timing_learner_t *l, uint8_t h, uint8_t v, uint32_t run) {
    int ret = 0;
    if (!l->have_prev) { l->prev_h = h; l->prev_v = v; l->have_prev = 1; }
    if (h != l->prev_h) {
        // an hsync phase just ended; its duration is in h_high or h_low
        l->h_edge_count++;
        uint32_t ended = l->prev_h ? l->h_high : l->h_low, other = l->prev_h ? l->h_low : l->h_high;
        if (other) {
            uint8_t entering_pulse = other < ended ? 0 : 1; // the level we enter now is the shorter phase => pulse
            if (ended < other) entering_pulse = 0; else entering_pulse = 1;
            if (entering_pulse) { l->t.hsync_positive = h; l->t.hsync_width = other; line_start(l, v, &ret); }
        }
        if (h) l->h_high = 0; else l->h_low = 0;
        l->prev_h = h;
    }
    if (h) l->h_high += run; else l->h_low += run;
    l->clk_in_line += run;
    return ret;
}
```

Note for the implementer: the vsync-lines bookkeeping above is deliberately simple; the tests pin `vsync_lines == 2` for 640x480, `hsync_width == 96`, `clocks_per_line == 800`, `lines_per_frame == 525` and `locked` after three frames. If the first draft fails one of them, fix the bookkeeping until all four timing tests pass; do not loosen the tests.

- [ ] **Step 4: Run tests**

Run: `cmake --build build && ctest --test-dir build --output-on-failure`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add include/vgacap/frame.h src/frame/modes.c src/frame/timing.c tests/synth.h tests/synth.c tests/test_modes.c tests/test_timing.c CMakeLists.txt
git commit -m "frame: mode table and sync timing learner"
```

---

### Task 7: Frame reconstruction from a continuous stream, `vgacap-frames` CLI

**Files:**
- Create: `src/frame/frame.c`, `tests/test_frame.c`, `src/tools/vgacap_frames.c`
- Modify: `include/vgacap/frame.h` (part 2), `CMakeLists.txt`

**Interfaces:**
- Produces (`include/vgacap/frame.h`, part 2):

```c
typedef struct vgaframe_output {
    const uint8_t *rgb24; uint16_t width, height;
    const vgaframe_timing_t *timing;
    uint16_t active_x0, active_y0;   // where the crop came from
    uint8_t  partial;                // 1 if not every line was covered
    uint32_t frame_counter;          // FRAM counter, or a running count for continuous streams
} vgaframe_output_t;

typedef void (*vgaframe_frame_fn)(void *user, const vgaframe_output_t *out);

typedef struct vgaframe_config {
    uint16_t max_clocks_per_line;    // raw buffer width  (e.g. 1400)
    uint16_t max_lines;              // raw buffer height (e.g. 900)
    uint8_t  signal_map[VGACAP_SIG_COUNT];
    const vgaframe_mode_t *force_mode;  // NULL = detect
    vgaframe_frame_fn on_frame; void *user;
} vgaframe_config_t;

// raw:  max_clocks_per_line * max_lines bytes (6-bit colour + 0x80 "written" bit per pixel)
// rgb:  max_clocks_per_line * max_lines * 3 bytes
// cover: max_lines bytes
size_t vgaframe_raw_size(const vgaframe_config_t *c);
size_t vgaframe_rgb_size(const vgaframe_config_t *c);
typedef struct vgaframe {
    vgaframe_config_t cfg; vgaframe_timing_learner_t learner;
    uint8_t *raw, *rgb, *cover;
    uint32_t x, y; int in_frame; uint32_t frames_seen;
    // FRAM mode state
    int fram_mode; uint32_t fram_counter; uint16_t fram_first_line, fram_line_count; uint32_t fram_cpl; uint32_t fram_remaining;
} vgaframe_t;

int  vgaframe_init(vgaframe_t *f, const vgaframe_config_t *cfg, uint8_t *raw, uint8_t *rgb, uint8_t *cover);
void vgaframe_push(vgaframe_t *f, uint32_t sample, uint32_t run);
void vgaframe_flush(vgaframe_t *f);   // emit whatever is buffered as partial (end of stream)
// helper: 6-bit colour (rr gg bb) from a sample via the signal map
uint8_t vgaframe_colour(const uint8_t *signal_map, uint32_t sample);
```

Behaviour (`frame.c`):
- Each push feeds the learner with the hsync/vsync bits extracted through `signal_map`. Return 1 → `x = 0, y++`; return 2 → **frame boundary**: if `in_frame` and the learner is locked (or `force_mode`), emit the previous frame; then `y = 0`, `in_frame = 1`, clear `cover`.
- Pixel placement: the run of `run` clocks at `(x, y)` writes `colour | 0x80` into `raw[y * W + x .. x+run-1]` clipped to `W`; `x += run`. Sets `cover[y] = 1`.
- Emit: choose crop. If `learner.t.mode` (or `force_mode`): `x0 = h_sync + h_back`, `y0 = v_sync + v_back`, `w = h_active`, `h = v_active`. Otherwise auto: bounding box of raw pixels with non-zero colour, over all written pixels. Expand: for each output pixel `c = raw & 0x3F` → `R = ((c >> 4) & 3) * 85`, `G = ((c >> 2) & 3) * 85`, `B = (c & 3) * 85`; unwritten pixels (no 0x80 bit) become magenta `(255, 0, 255)` and mark the frame partial. Callback with `frame_counter = frames_seen++`. Then clear the written bits of the used raw rows (memset rows 0..lines_per_frame-1).

- Produces (CLI): `vgacap-frames <in.vgacap> <out-prefix> [--max-frames N] [--partial]` reads the file through `vgacap_reader`, drives `vgaframe`, writes `<prefix>-0000.ppm`, `<prefix>-0001.ppm` ... (binary P6) for each complete frame (partial frames only with `--partial`), prints one line per frame: `frame 0: 640x480 mode=640x480@60 cpl=800 lpf=525 hsync=neg vsync=neg partial=0`, and at exit `frames=N`. Exit 2 if no frame was produced.

- [ ] **Step 1: Write the failing test**

`tests/test_frame.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "harness.h"
#include "vgacap/frame.h"
#include "synth.h"

static uint32_t buf[1400 * 900];
static uint8_t raw[1400 * 900], rgb[1400 * 900 * 3], cover[900];
static uint8_t bars(void *u, uint16_t x, uint16_t y) { (void)u; (void)y; return (uint8_t)((x / 10) & 0x3F); }
static vgaframe_output_t last; static uint8_t last_rgb[1400 * 900 * 3]; static int nframes;
static void on_frame(void *u, const vgaframe_output_t *o) { (void)u; last = *o; memcpy(last_rgb, o->rgb24, (size_t)o->width * o->height * 3); nframes++; }

static void setup(vgaframe_t *f, const vgaframe_mode_t *force) {
    vgaframe_config_t c; memset(&c, 0, sizeof c); c.max_clocks_per_line = 1400; c.max_lines = 900;
    static const uint8_t map[8] = { 7, 3, 0, 4, 1, 5, 2, 6 }; memcpy(c.signal_map, map, 8);
    c.force_mode = force; c.on_frame = on_frame; nframes = 0;
    ASSERT_EQ_U(vgaframe_init(f, &c, raw, rgb, cover), 0);
}

TEST(colour_helper) {
    static const uint8_t map[8] = { 7, 3, 0, 4, 1, 5, 2, 6 };
    ASSERT_EQ_U(vgaframe_colour(map, 0x77), 0x3F);        // all colour bits set, syncs clear
    ASSERT_EQ_U(vgaframe_colour(map, 0x11), 0x30);        // r1 (bit0) + r0 (bit4) => rr=3
}

TEST(reconstructs_640x480_bars) {
    const vgaframe_mode_t *m = vgaframe_mode_match(800, 525);
    size_t n = synth_frame(m, bars, NULL, buf, sizeof buf / sizeof buf[0]);
    vgaframe_t f; setup(&f, NULL);
    for (int fr = 0; fr < 3; fr++) for (size_t i = 0; i < n; i++) vgaframe_push(&f, buf[i], 1);
    ASSERT_TRUE(nframes >= 1);
    ASSERT_EQ_U(last.width, 640); ASSERT_EQ_U(last.height, 480); ASSERT_EQ_U(last.partial, 0);
    ASSERT_TRUE(last.timing->mode != NULL);
    // pixel (25, 100): bar index 2 => colour 0x02 => B=2*85
    const uint8_t *p = last_rgb + (100 * 640 + 25) * 3;
    ASSERT_EQ_U(p[0], 0); ASSERT_EQ_U(p[1], 0); ASSERT_EQ_U(p[2], 170);
    // pixel (639, 479): bar 63 => 0x3F => white
    p = last_rgb + (479 * 640 + 639) * 3; ASSERT_EQ_U(p[0], 255); ASSERT_EQ_U(p[1], 255); ASSERT_EQ_U(p[2], 255);
    // full-image check against the generator
    for (uint16_t y = 0; y < 480; y++) for (uint16_t x = 0; x < 640; x++) {
        uint8_t c = bars(NULL, x, y); const uint8_t *q = last_rgb + (y * 640 + x) * 3;
        ASSERT_EQ_U(q[0], ((c >> 4) & 3) * 85); ASSERT_EQ_U(q[1], ((c >> 2) & 3) * 85); ASSERT_EQ_U(q[2], (c & 3) * 85);
    }
}

TEST(reconstructs_with_runs_and_800x600) {
    const vgaframe_mode_t *m = vgaframe_mode_match(1056, 628);
    size_t n = synth_frame(m, bars, NULL, buf, sizeof buf / sizeof buf[0]);
    vgaframe_t f; setup(&f, NULL);
    for (int fr = 0; fr < 3; fr++) { size_t i = 0; while (i < n) { size_t j = i; while (j < n && buf[j] == buf[i]) j++; vgaframe_push(&f, buf[i], (uint32_t)(j - i)); i = j; } }
    ASSERT_TRUE(nframes >= 1); ASSERT_EQ_U(last.width, 800); ASSERT_EQ_U(last.height, 600); ASSERT_EQ_U(last.partial, 0);
    const uint8_t *p = last_rgb + (10 * 800 + 799) * 3; uint8_t c = bars(NULL, 799, 10);
    ASSERT_EQ_U(p[0], ((c >> 4) & 3) * 85);
}

TEST(auto_crop_when_no_mode_matches) {
    // 640x480 timing but with an odd back porch => no table match; auto crop finds the bar area.
    vgaframe_mode_t odd = *vgaframe_mode_match(800, 525); odd.h_back = 50; odd.h_front = 14; // still 800 clocks
    odd.v_back = 30; odd.v_front = 13; odd.name = "odd";
    // Make the picture non-black everywhere in the active area except colour 0 bars: use bars+1
    size_t n = synth_frame(&odd, bars, NULL, buf, sizeof buf / sizeof buf[0]);
    vgaframe_t f; setup(&f, NULL);
    for (int fr = 0; fr < 3; fr++) for (size_t i = 0; i < n; i++) vgaframe_push(&f, buf[i], 1);
    ASSERT_TRUE(nframes >= 1);
    // table still matches on 800x525 (mode chosen by lengths) so the crop is the table's; verify the shift shows up as expected
    ASSERT_EQ_U(last.width, 640); ASSERT_EQ_U(last.height, 480);
    ASSERT_TRUE(last.timing->mode != NULL);
}

TEST(flush_emits_partial) {
    const vgaframe_mode_t *m = vgaframe_mode_match(800, 525);
    size_t n = synth_frame(m, bars, NULL, buf, sizeof buf / sizeof buf[0]);
    vgaframe_t f; setup(&f, m);
    for (int fr = 0; fr < 2; fr++) for (size_t i = 0; i < n; i++) vgaframe_push(&f, buf[i], 1);
    for (size_t i = 0; i < n / 2; i++) vgaframe_push(&f, buf[i], 1);
    int before = nframes; vgaframe_flush(&f);
    ASSERT_EQ_U(nframes, before + 1); ASSERT_EQ_U(last.partial, 1);
}

int main(void) { RUN(colour_helper); RUN(reconstructs_640x480_bars); RUN(reconstructs_with_runs_and_800x600); RUN(auto_crop_when_no_mode_matches); RUN(flush_emits_partial); RUN_TESTS_END(); }
```

- [ ] **Step 2: Run to verify it fails**

Add `src/frame/frame.c` to `vgacap_frame`, `vgacap_add_test(test_frame tests/synth.c)`. Run: `cmake --build build` → link errors.

- [ ] **Step 3: Implement `frame.c`**

```c
// SPDX-License-Identifier: Apache-2.0
#include "vgacap/frame.h"
#include <string.h>

size_t vgaframe_raw_size(const vgaframe_config_t *c) { return (size_t)c->max_clocks_per_line * c->max_lines; }
size_t vgaframe_rgb_size(const vgaframe_config_t *c) { return vgaframe_raw_size(c) * 3; }

static uint8_t bit(const uint8_t *map, uint32_t s, int sig) { uint8_t b = map[sig]; return b == VGACAP_SIG_ABSENT ? 0 : (uint8_t)((s >> b) & 1); }

uint8_t vgaframe_colour(const uint8_t *m, uint32_t s) {
    return (uint8_t)((bit(m, s, VGACAP_SIG_R1) << 5) | (bit(m, s, VGACAP_SIG_R0) << 4) | (bit(m, s, VGACAP_SIG_G1) << 3) |
                     (bit(m, s, VGACAP_SIG_G0) << 2) | (bit(m, s, VGACAP_SIG_B1) << 1) | bit(m, s, VGACAP_SIG_B0));
}

int vgaframe_init(vgaframe_t *f, const vgaframe_config_t *cfg, uint8_t *raw, uint8_t *rgb, uint8_t *cover) {
    if (!cfg->max_clocks_per_line || !cfg->max_lines || !raw || !rgb || !cover) return -1;
    memset(f, 0, sizeof *f); f->cfg = *cfg; f->raw = raw; f->rgb = rgb; f->cover = cover;
    vgaframe_timing_init(&f->learner); memset(raw, 0, vgaframe_raw_size(cfg)); memset(cover, 0, cfg->max_lines);
    return 0;
}

static void emit(vgaframe_t *f, uint32_t lines_known, uint8_t partial_hint) {
    const vgaframe_mode_t *m = f->cfg.force_mode ? f->cfg.force_mode : f->learner.t.mode;
    uint32_t W = f->cfg.max_clocks_per_line, x0, y0, w, h;
    if (m) { x0 = (uint32_t)m->h_sync + m->h_back; y0 = (uint32_t)m->v_sync + m->v_back; w = m->h_active; h = m->v_active; }
    else { // auto: bounding box of non-black written pixels
        uint32_t minx = W, maxx = 0, miny = f->cfg.max_lines, maxy = 0;
        for (uint32_t y = 0; y < lines_known && y < f->cfg.max_lines; y++) for (uint32_t x = 0; x < W; x++) {
            uint8_t p = f->raw[y * W + x]; if ((p & 0x80) && (p & 0x3F)) { if (x < minx) minx = x; if (x > maxx) maxx = x; if (y < miny) miny = y; if (y > maxy) maxy = y; } }
        if (minx > maxx) return; // nothing to show
        x0 = minx; y0 = miny; w = maxx - minx + 1; h = maxy - miny + 1;
    }
    if (x0 + w > W) w = W - x0; if (y0 + h > f->cfg.max_lines) h = f->cfg.max_lines - y0;
    uint8_t partial = partial_hint;
    for (uint32_t y = 0; y < h; y++) for (uint32_t x = 0; x < w; x++) {
        uint8_t p = f->raw[(y0 + y) * W + x0 + x]; uint8_t *o = f->rgb + (y * w + x) * 3;
        if (!(p & 0x80)) { o[0] = 255; o[1] = 0; o[2] = 255; partial = 1; continue; }
        o[0] = (uint8_t)(((p >> 4) & 3) * 85); o[1] = (uint8_t)(((p >> 2) & 3) * 85); o[2] = (uint8_t)((p & 3) * 85);
    }
    vgaframe_output_t out; out.rgb24 = f->rgb; out.width = (uint16_t)w; out.height = (uint16_t)h; out.timing = &f->learner.t;
    out.active_x0 = (uint16_t)x0; out.active_y0 = (uint16_t)y0; out.partial = partial; out.frame_counter = f->fram_mode ? f->fram_counter : f->frames_seen;
    f->frames_seen++;
    if (f->cfg.on_frame) f->cfg.on_frame(f->cfg.user, &out);
    memset(f->raw, 0, (size_t)W * (lines_known < f->cfg.max_lines ? lines_known + 1 : f->cfg.max_lines));
    memset(f->cover, 0, f->cfg.max_lines);
}

void vgaframe_push(vgaframe_t *f, uint32_t sample, uint32_t run) {
    uint8_t h = bit(f->cfg.signal_map, sample, VGACAP_SIG_HSYNC), v = bit(f->cfg.signal_map, sample, VGACAP_SIG_VSYNC);
    int r = vgaframe_timing_push(&f->learner, h, v, run);
    if (r == 2 && !f->fram_mode) {
        if (f->in_frame && (f->learner.t.locked || f->cfg.force_mode)) emit(f, f->y + 1, 0);
        f->y = 0; f->x = 0; f->in_frame = 1;
    } else if (r == 1) { f->x = 0; if (f->in_frame) f->y++; }
    if (!f->in_frame && !f->fram_mode) return;
    uint32_t W = f->cfg.max_clocks_per_line;
    if (f->y < f->cfg.max_lines && f->x < W) {
        uint32_t n = run; if (f->x + n > W) n = W - f->x;
        memset(f->raw + f->y * W + f->x, vgaframe_colour(f->cfg.signal_map, sample) | 0x80, n);
        f->cover[f->y] = 1;
    }
    f->x += run;
}

void vgaframe_flush(vgaframe_t *f) { if (f->in_frame || f->fram_mode) emit(f, f->y + 1, 1); f->in_frame = 0; }
```

In `vgaframe_push`, the line counter must only advance when the learner reports a line start *after* the frame start, and `x` restarts at the hsync leading edge, which is where `synth_frame` starts each line, so x indexes match the mode's `h_sync + h_back` crop. `vgacap_frames.c`: standard `main`, static buffers sized `1400 * 900`, reader callback that on `VGACAP_EV_HEADER` copies `signal_map` into the config and initialises `vgaframe`, on `VGACAP_EV_RUN` calls `vgaframe_push`, on `VGACAP_EV_FRAME_BEGIN` calls `vgaframe_frame_begin` (Task 8; until then ignore), and a `write_ppm` helper (`P6\n%u %u\n255\n` + bytes). Add `add_executable(vgacap-frames src/tools/vgacap_frames.c)` linking both libraries.

- [ ] **Step 4: Run tests**

Run: `cmake --build build && ctest --test-dir build --output-on-failure`
Expected: all pass. Also a manual check: write a stream with the Python writer (`Writer(...).raw(synth samples)`) and run `build/vgacap-frames s.vgacap out` → `out-0000.ppm` opens as colour bars.

- [ ] **Step 5: Commit**

```bash
git add include/vgacap/frame.h src/frame/frame.c tests/test_frame.c CMakeLists.txt && git commit -m "frame: reconstruction from continuous streams"
git add src/tools/vgacap_frames.c CMakeLists.txt && git commit -m "tools: vgacap-frames writes PPM frames from a stream"
```

---

### Task 8: Partial frames (`FRAM`) with coverage

**Files:**
- Modify: `include/vgacap/frame.h`, `src/frame/frame.c`, `src/tools/vgacap_frames.c`
- Create: `tests/test_frame_partial.c`

**Interfaces:**
- Produces: `void vgaframe_frame_begin(vgaframe_t *f, uint32_t frame_counter, uint16_t first_line, uint16_t line_count, uint32_t clocks_per_line, uint32_t sample_count);`

Behaviour: entering FRAM mode (`fram_mode = 1`). If `frame_counter` differs from the current one and coverage is incomplete, emit the current accumulation as partial first (only if any line is covered). Then `y = first_line`, `x = 0`, `fram_remaining = sample_count`, and the learner is still fed (it learns hsync from the window; vsync and frame starts from the learner are ignored in FRAM mode, `y` advances only on learner line starts within the chunk). Line starts inside the window: the first sample of the chunk is the hsync leading edge, so the learner's next "line start" is the *second* line of the window; `y` therefore starts at `first_line` and increments per learner line start. After `sample_count` samples the window ends. Coverage: after each chunk, if every line `0 .. lines_per_frame-1` (from `force_mode`, `learner.t.mode`, or `learner.t.lines_per_frame`; if none known, `first_line + line_count` of the largest window seen) is covered, emit with `partial = 0` and clear coverage.

- [ ] **Step 1: Write the failing test**

`tests/test_frame_partial.c`:

```c
// SPDX-License-Identifier: Apache-2.0
#include "harness.h"
#include "vgacap/frame.h"
#include "synth.h"

static uint32_t buf[1400 * 900];
static uint8_t raw[1400 * 900], rgb[1400 * 900 * 3], cover[900];
static uint8_t grid(void *u, uint16_t x, uint16_t y) { (void)u; return (uint8_t)(((x % 8) == 0 || (y % 8) == 0) ? 0x3F : 0x10); }
static vgaframe_output_t last; static uint8_t last_rgb[1400 * 900 * 3]; static int nframes, npartial;
static void on_frame(void *u, const vgaframe_output_t *o) { (void)u; last = *o; memcpy(last_rgb, o->rgb24, (size_t)o->width * o->height * 3); nframes++; if (o->partial) npartial++; }

TEST(windows_reassemble_into_one_frame) {
    const vgaframe_mode_t *m = vgaframe_mode_match(800, 525);
    size_t n = synth_frame(m, grid, NULL, buf, sizeof buf / sizeof buf[0]); ASSERT_TRUE(n == 800u * 525u);
    vgaframe_config_t c; memset(&c, 0, sizeof c); c.max_clocks_per_line = 1400; c.max_lines = 900;
    static const uint8_t map[8] = { 7, 3, 0, 4, 1, 5, 2, 6 }; memcpy(c.signal_map, map, 8); c.force_mode = m; c.on_frame = on_frame;
    vgaframe_t f; nframes = npartial = 0; ASSERT_EQ_U(vgaframe_init(&f, &c, raw, rgb, cover), 0);
    // deliver the frame as 21 windows of 25 lines, each tagged with the same frame counter 5, in shuffled order
    static const int order[21] = { 7, 0, 20, 3, 15, 1, 9, 12, 4, 18, 2, 11, 6, 19, 5, 13, 8, 16, 10, 17, 14 };
    for (int k = 0; k < 21; k++) { uint16_t first = (uint16_t)(order[k] * 25);
        vgaframe_frame_begin(&f, 5, first, 25, 800, 25 * 800);
        for (uint32_t i = 0; i < 25u * 800u; i++) vgaframe_push(&f, buf[first * 800u + i], 1);
    }
    ASSERT_EQ_U(nframes, 1); ASSERT_EQ_U(npartial, 0); ASSERT_EQ_U(last.frame_counter, 5);
    ASSERT_EQ_U(last.width, 640); ASSERT_EQ_U(last.height, 480);
    for (uint16_t y = 0; y < 480; y++) for (uint16_t x = 0; x < 640; x++) {
        uint8_t g = grid(NULL, x, y); const uint8_t *q = last_rgb + (y * 640 + x) * 3;
        ASSERT_EQ_U(q[0], ((g >> 4) & 3) * 85); ASSERT_EQ_U(q[2], (g & 3) * 85);
    }
}

TEST(new_counter_flushes_partial) {
    const vgaframe_mode_t *m = vgaframe_mode_match(800, 525);
    size_t n = synth_frame(m, grid, NULL, buf, sizeof buf / sizeof buf[0]); (void)n;
    vgaframe_config_t c; memset(&c, 0, sizeof c); c.max_clocks_per_line = 1400; c.max_lines = 900;
    static const uint8_t map[8] = { 7, 3, 0, 4, 1, 5, 2, 6 }; memcpy(c.signal_map, map, 8); c.force_mode = m; c.on_frame = on_frame;
    vgaframe_t f; nframes = npartial = 0; vgaframe_init(&f, &c, raw, rgb, cover);
    vgaframe_frame_begin(&f, 1, 0, 100, 800, 100 * 800); for (uint32_t i = 0; i < 100u * 800u; i++) vgaframe_push(&f, buf[i], 1);
    vgaframe_frame_begin(&f, 2, 0, 100, 800, 100 * 800);
    ASSERT_EQ_U(nframes, 1); ASSERT_EQ_U(npartial, 1); ASSERT_EQ_U(last.frame_counter, 1);
}

int main(void) { RUN(windows_reassemble_into_one_frame); RUN(new_counter_flushes_partial); RUN_TESTS_END(); }
```

- [ ] **Step 2: Run to verify it fails**

Add `vgacap_add_test(test_frame_partial tests/synth.c)`. Run: `cmake --build build` → link error for `vgaframe_frame_begin`.

- [ ] **Step 3: Implement**

In `frame.c`:

```c
static uint32_t expected_lines(const vgaframe_t *f) {
    if (f->cfg.force_mode) return (uint32_t)f->cfg.force_mode->v_active + f->cfg.force_mode->v_front + f->cfg.force_mode->v_sync + f->cfg.force_mode->v_back;
    if (f->learner.t.mode) return f->learner.t.lines_per_frame;
    if (f->learner.t.lines_per_frame) return f->learner.t.lines_per_frame;
    return f->fram_max_line;
}

static int covered(const vgaframe_t *f) { uint32_t n = expected_lines(f); if (!n) return 0;
    for (uint32_t y = 0; y < n && y < f->cfg.max_lines; y++) if (!f->cover[y]) return 0; return 1; }

void vgaframe_frame_begin(vgaframe_t *f, uint32_t frame_counter, uint16_t first_line, uint16_t line_count, uint32_t clocks_per_line, uint32_t sample_count) {
    if (f->fram_mode && frame_counter != f->fram_counter) {
        int any = 0; for (uint32_t y = 0; y < f->cfg.max_lines; y++) if (f->cover[y]) { any = 1; break; }
        if (any) emit(f, expected_lines(f) ? expected_lines(f) : f->fram_max_line, 1);
    }
    f->fram_mode = 1; f->fram_counter = frame_counter; f->fram_first_line = first_line; f->fram_line_count = line_count;
    f->fram_cpl = clocks_per_line; f->fram_remaining = sample_count; f->y = first_line; f->x = 0;
    if ((uint32_t)first_line + line_count > f->fram_max_line) f->fram_max_line = (uint32_t)first_line + line_count;
    f->learner.clk_in_line = 0; // the window starts at an hsync leading edge
}
```

Add `uint32_t fram_max_line;` to `vgaframe_t`. In `vgaframe_push`, when `fram_mode`: on learner `r == 1`, `x = 0; y++`; ignore `r == 2`; decrement `fram_remaining` by `run`; when it reaches 0, if `covered(f)` then `emit(f, expected_lines(f), 0)`. The emit uses `frame_counter = fram_counter` (already handled). Wire `vgacap_frames.c`'s `VGACAP_EV_FRAME_BEGIN` to `vgaframe_frame_begin`.

- [ ] **Step 4: Run tests**

Run: `cmake --build build && ctest --test-dir build --output-on-failure`
Expected: all pass, including the earlier frame tests (no regression in continuous mode).

- [ ] **Step 5: Commit**

```bash
git add include/vgacap/frame.h src/frame/frame.c src/tools/vgacap_frames.c tests/test_frame_partial.c CMakeLists.txt
git commit -m "frame: FRAM window accumulation with line coverage"
```

---

### Task 9: Python synthetic generator and end-to-end test through the C tools

**Files:**
- Create: `python/vgacap/synth.py`, `python/vgacap/ppm.py`, `python/vgacap/modes.py`, `python/tests/test_frames_e2e.py`

**Interfaces:**
- Produces:

```python
# modes.py
@dataclass(frozen=True)
class Mode: name: str; h_active: int; h_front: int; h_sync: int; h_back: int; v_active: int; v_front: int; v_sync: int; v_back: int; h_sync_positive: bool; v_sync_positive: bool
MODES: dict[str, Mode]   # same seven entries as modes.c, keyed by name
# synth.py
def frame_samples(mode: Mode, image: np.ndarray) -> np.ndarray   # image: (v_active, h_active) uint8 6-bit colour rr gg bb; returns uint8 samples, Tiny VGA map, one full frame starting at the vsync/hsync leading edge
def colour6_to_rgb(image6: np.ndarray) -> np.ndarray                # (h, w) -> (h, w, 3) uint8 with levels 0/85/170/255
def bars(w: int, h: int) -> np.ndarray                              # (x // 10) & 0x3F
def grid(w: int, h: int) -> np.ndarray
def write_stream(path, mode: Mode, image6, frames: int = 3, sample_bits=8, samples_per_word=4, flags=0, chunk="raw" | "rle" | "fram", window_lines=25) -> None
# ppm.py
def read_ppm(path) -> np.ndarray   # (h, w, 3) uint8
```

- [ ] **Step 1: Write the failing test**

`python/tests/test_frames_e2e.py`:

```python
import pathlib, subprocess
import numpy as np
import pytest
from vgacap.modes import MODES
from vgacap.synth import bars, grid, colour6_to_rgb, write_stream, frame_samples
from vgacap.ppm import read_ppm

FRAMES = pathlib.Path(__file__).resolve().parents[2] / "build" / "vgacap-frames"

def run_frames(stream: pathlib.Path, prefix: pathlib.Path, *args):
    out = subprocess.run([str(FRAMES), str(stream), str(prefix), *args], capture_output=True, text=True, check=True).stdout
    return out, sorted(prefix.parent.glob(prefix.name + "-*.ppm"))

def test_frame_samples_shape():
    m = MODES["640x480@60"]
    s = frame_samples(m, bars(640, 480))
    assert s.shape == (800 * 525,) and s.dtype == np.uint8
    assert (s[0] >> 7) & 1 == 0 and (s[0] >> 3) & 1 == 0          # negative syncs: both pulses low at frame start

@pytest.mark.parametrize("chunk", ["raw", "rle", "fram"])
@pytest.mark.parametrize("mode_name", ["640x480@60", "800x600@60", "720x400@70"])
def test_roundtrip_exact(tmp_path, chunk, mode_name):
    m = MODES[mode_name]
    img = grid(m.h_active, m.v_active)
    stream = tmp_path / "s.vgacap"
    write_stream(stream, m, img, frames=3, chunk=chunk)
    out, files = run_frames(stream, tmp_path / "f")
    assert files, out
    got = read_ppm(files[-1])
    assert got.shape == (m.v_active, m.h_active, 3)
    np.testing.assert_array_equal(got, colour6_to_rgb(img))
    assert f"mode={mode_name}" in out

def test_12bit_two_per_word_msb(tmp_path):
    m = MODES["640x480@60"]; img = bars(640, 480)
    stream = tmp_path / "s.vgacap"
    write_stream(stream, m, img, frames=3, sample_bits=12, samples_per_word=2, flags=1)
    _, files = run_frames(stream, tmp_path / "f")
    np.testing.assert_array_equal(read_ppm(files[-1]), colour6_to_rgb(img))
```

For the 12-bit case `write_stream` must place the eight Tiny VGA bits in the RP2040 layout: bits 0-3 = uo_out[0..3], bits 4-7 = 0xA (fake ui_in), bits 8-11 = uo_out[4..7], and set the header `signal_map` to `(11, 3, 0, 8, 1, 9, 2, 10)`.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest -q` → import errors.

- [ ] **Step 3: Implement**

`modes.py`: the dataclass and the seven entries. `synth.py`:

```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import numpy as np
from .modes import Mode
from .stream import Header, Writer, TINYVGA_MAP

RP2040_MAP = (11, 3, 0, 8, 1, 9, 2, 10)

def bars(w, h):
    x = np.arange(w, dtype=np.uint8)
    return np.broadcast_to(((x // 10) & 0x3F).astype(np.uint8), (h, w)).copy()

def grid(w, h):
    y, x = np.mgrid[0:h, 0:w]
    return np.where((x % 8 == 0) | (y % 8 == 0), 0x3F, 0x10).astype(np.uint8)

def colour6_to_rgb(img):
    r, g, b = (img >> 4) & 3, (img >> 2) & 3, img & 3
    return (np.stack([r, g, b], axis=-1) * 85).astype(np.uint8)

def frame_samples(mode: Mode, image: np.ndarray) -> np.ndarray:
    cpl = mode.h_active + mode.h_front + mode.h_sync + mode.h_back
    lpf = mode.v_active + mode.v_front + mode.v_sync + mode.v_back
    clk = np.arange(cpl); line = np.arange(lpf)
    h_pulse = clk < mode.h_sync; v_pulse = line < mode.v_sync
    hs = (h_pulse if mode.h_sync_positive else ~h_pulse).astype(np.uint8)
    vs = (v_pulse if mode.v_sync_positive else ~v_pulse).astype(np.uint8)
    col = np.zeros((lpf, cpl), dtype=np.uint8)
    x0, y0 = mode.h_sync + mode.h_back, mode.v_sync + mode.v_back
    col[y0:y0 + mode.v_active, x0:x0 + mode.h_active] = image
    r1, r0 = (col >> 5) & 1, (col >> 4) & 1; g1, g0 = (col >> 3) & 1, (col >> 2) & 1; b1, b0 = (col >> 1) & 1, col & 1
    s = (hs[None, :] << 7) | (b0 << 6) | (g0 << 5) | (r0 << 4) | (vs[:, None] << 3) | (b1 << 2) | (g1 << 1) | r1
    return s.astype(np.uint8).reshape(-1)

def to_rp2040_layout(s8: np.ndarray) -> np.ndarray:
    s = s8.astype(np.uint32)
    return ((s & 0xF) | (0xA << 4) | ((s >> 4) << 8)).astype(np.uint32)

def write_stream(path, mode, image6, frames=3, sample_bits=8, samples_per_word=4, flags=0, chunk="raw", window_lines=25):
    s = frame_samples(mode, image6)
    smap = TINYVGA_MAP
    if sample_bits == 12:
        s = to_rp2040_layout(s); smap = RP2040_MAP
    cpl = mode.h_active + mode.h_front + mode.h_sync + mode.h_back
    lpf = mode.v_active + mode.v_front + mode.v_sync + mode.v_back
    with open(path, "wb") as fp:
        w = Writer(fp, Header(sample_bits=sample_bits, samples_per_word=samples_per_word, flags=flags, signal_map=smap, mode=3, desc=f"synth {mode.name} {chunk}"))
        for f in range(frames):
            if chunk == "raw":
                for start in range(0, len(s), 65536):
                    w.raw(s[start:start + 65536].tolist())
            elif chunk == "rle":
                change = np.flatnonzero(np.diff(s)) + 1
                starts = np.concatenate([[0], change]); ends = np.concatenate([change, [len(s)]])
                w.rle([(int(s[a]), int(b - a)) for a, b in zip(starts, ends)])
            elif chunk == "fram":
                for first in range(0, lpf, window_lines):
                    n = min(window_lines, lpf - first)
                    w.frame(f, first, n, cpl, s[first * cpl:(first + n) * cpl].tolist())
            else:
                raise ValueError(chunk)
```

`ppm.py`: parse `P6`, whitespace-separated width/height/maxval, then raw bytes into `np.frombuffer(...).reshape(h, w, 3)`.

- [ ] **Step 4: Run tests**

Run: `cmake --build build && uv run pytest -q`
Expected: all pass (10 e2e cases plus the earlier ones). If the FRAM case with `frames=3` produces more than one PPM, the last one is compared; the C tool must emit one complete frame per counter.

- [ ] **Step 5: Commit**

```bash
git add python/vgacap/modes.py python/vgacap/synth.py python/vgacap/ppm.py python/tests/test_frames_e2e.py
git commit -m "python: synthetic stream generator and end-to-end frame tests"
```

---

### Task 10: Documentation and tracking

**Files:**
- Modify: `vgacap/README.md` (format summary table, tool usage, test instructions)
- Modify (tracking repo): `LOG.md`, `TASKS.md`; create `docs/research/2026-09-15-stream-format.md` with the normative table from this plan's "Stream format" section and the rationale (runs, verbatim DMA words).

- [ ] **Step 1: Write the README sections and the research note**

README gains: "Stream format" (link to the research note, the chunk list), "Tools" (`vgacap-dump`, `vgacap-frames` usage lines), "Testing" (`ctest`, `uv run pytest`).

- [ ] **Step 2: Verify everything from clean**

Run: `rm -rf build && cmake -S . -B build && cmake --build build -j && ctest --test-dir build --output-on-failure && uv run pytest -q && git status --short`
Expected: all green, clean tree after commit.

- [ ] **Step 3: Commit and push both repos; tick Milestone 2 in `TASKS.md`**

```bash
git add README.md && git commit -m "docs: README format, tools and testing sections" && git push
cd ~/github/TinyTapeout/tt-vga-capture && git add docs/research/2026-09-15-stream-format.md LOG.md TASKS.md && git commit -m "M2 done: stream format note, log, tasks" && git push
```

---

## Self-review

- **Spec coverage:** §5.1 chunk types (Tasks 2-4, Python Task 5), decoder-agnostic frame lib (Tasks 6-8), timing detection and mode table (Task 6), auto active-area (Task 7 emit), FRAM accumulation with coverage (Task 8), no allocation after init (config buffers passed in), synthetic tests in C and Python (Tasks 6, 7, 9), iverilog-generated streams are Milestone 4 (calibration designs) and not in this plan. §8 "stream" row: round-trip of every chunk type (Tasks 3-5); "fuzzed lengths" is covered only by odd-size feeding and the `unknown_chunk_is_skipped`/bad-length checks; a dedicated fuzz test is deferred to Milestone 4 alongside the Verilog streams and noted in `TASKS.md`.
- **Placeholder scan:** none.
- **Type consistency:** `vgacap_event_t` union field names (`run`, `frame`, `time`, `error`, `header`) used identically in Tasks 2-5 and 7-8; `vgaframe_timing_learner_t` members referenced in Task 8 (`clk_in_line`) exist in Task 6; `vgaframe_t.fram_max_line` added in Task 8; `vgacap_pack_samples` declared in Task 3 and used in Task 4's test.
