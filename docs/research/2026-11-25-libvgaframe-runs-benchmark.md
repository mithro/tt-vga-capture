# libvgaframe on run-length input: cost per clock

Date: 2026-11-25. Task 2 of the Milestone 10 plan.

## Question

The simulation pipeline will feed libvgaframe up to about 1.5e9 clocks per
project. The spec budgets 5% of the fastest simulation's 220 ns/clock, which is
11 ns/clock, for all post-simulation work (frame reconstruction, samplers,
hashing). How much of that does `vgaframe_push` alone use?

## Method

- Code: vgacap branch `m10-bench` (`bench/bench_runs.c`, target `bench-runs`,
  not a CTest test). It builds one 640x480@60 frame (800 x 525 = 420000 clocks,
  Tiny VGA samples from `tests/synth.c`), merges consecutive equal samples into
  (sample, run) pairs once, then replays those runs through `vgaframe_push`
  until exactly N clocks are pushed (the last pass is cut short). Buffers
  follow the spec: `max_clocks_per_line = 7596`, `max_lines = 1200`.
- Profiles: `busy` (a new colour every clock in the active area, `(x+y)&63`),
  `bars` (64 bars of 10 clocks), `static` (one colour).
- Only the replay loop is timed (`clock_gettime(CLOCK_MONOTONIC)`); setup is not.
- Build: `cmake -S . -B build-rel -DCMAKE_BUILD_TYPE=Release`, giving
  `-O3 -DNDEBUG -std=gnu99 -Wall -Wextra -Werror -Wshadow -Wconversion`.
- Host: big-storage, Intel Xeon Gold 6152 @ 2.10 GHz, `nproc` = 88. `uptime`
  at the start of the runs: load average 95.33 / 51.02 / 36.49 (about 1.1 per
  core, the normal level for this host, so some contention is possible); at
  the end 115.99 / 89.56 / 56.63.
- Each profile run 3 times at 1.5e9 clocks, sequentially; median reported.

## Results

All nine runs (`clocks=1500000000`, `frames=3570` every time; 1.5e9 / 420000 is
3571.4, so 3570 is the expected floor minus one for the first frame):

| profile | runs | seconds (3 runs) | ns/clock (3 runs) | median ns/clock | median ns/run |
|---|---|---|---|---|---|
| busy   | 1102539928 | 69.364, 67.539, 68.510 | 46.243, 45.026, 45.673 | 45.673 | 62.138 |
| bars   | 113463280  | 13.200, 16.035, 15.985 | 8.800, 10.690, 10.657  | 10.657 | 140.885 |
| static | 7178540    | 10.189, 7.303, 7.496   | 6.793, 4.868, 4.997    | 4.997  | 1044.247 |

The three median lines in the bench's own format are the runs with the median
`ns_per_clock`:

```
profile=busy clocks=1500000000 runs=1102539928 seconds=68.510 ns_per_clock=45.673 ns_per_run=62.138 frames=3570
profile=bars clocks=1500000000 runs=113463280 seconds=15.985 ns_per_clock=10.657 ns_per_run=140.885 frames=3570
profile=static clocks=1500000000 runs=7178540 seconds=7.496 ns_per_clock=4.997 ns_per_run=1044.247 frames=3570
```

Spread is large for `bars` and `static`: the first run was 20 to 35% slower
than the other two. Cause unknown. Treat `bars` as 8.8 to 10.7 ns/clock.

## Against the 11 ns/clock budget

- `static`: 5.0 ns/clock, leaves about 6.0 ns/clock (55%) for the samplers.
- `bars`: 10.7 ns/clock, leaves about 0.3 ns/clock. The best run (8.8) left 2.2.
  Effectively the whole budget.
- `busy`: 45.7 ns/clock, which is **34.7 ns/clock over** the budget (4.2x it).
  Nothing is left for samplers, and libvgaframe alone would cost about
  21% of a 220 ns/clock simulation, not 5%. At 1.5e9 clocks that is 68 s of
  libvgaframe time per project.

Cost is dominated by the per-run work, not per clock: about 62 ns/run on busy
(one clock per run) and 141 ns/run on bars. Static's roughly 1 us/run is
**hypothesis, not measured**: each of its runs is about 209 clocks and so a long
`memset`, but nothing here separates that from the learner's cost over those
clocks.

## What costs it (gprof)

`perf` is not installed on big-storage, so this uses gprof. Build: a separate
`build-pg/` with `-DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS=-pg
-DCMAKE_EXE_LINKER_FLAGS=-pg`. One run, `bench-runs --clocks 100000000
--profile busy`, on the shared host (load average 41.55 at the start; another
build was running on the host at the same time):

```
profile=busy clocks=100000000 runs=73483645 seconds=5.441 ns_per_clock=54.410 ns_per_run=74.043 frames=237
```

(The `-pg` instrumentation makes it slower: 54.4 ns/clock against 45.7 for the
Release build.) gprof's flat profile, total 1.79 s of samples:

| function | self s | % of samples | % of wall (5.441 s) |
|---|---|---|---|
| `vgaframe_push` (own body) | 0.51 | 28.2 | 9.4 |
| `vgaframe_colour` (called per push, 73174930 calls) | 0.48 | 26.8 | 8.8 |
| `vgaframe_timing_push` | 0.34 | 19.0 | 6.2 |
| `emit` (237 frames) | 0.17 | 9.5 | 3.1 |
| `main` (replay loop) | 0.13 | 7.3 | 2.4 |
| `_init`, `vgaframe_init`, others | 0.16 | 9.2 | 2.9 |

**gprof covers only 1.79 s of the 5.441 s wall time (33%).** The other 3.65 s
(67%) is not attributed: libc is not built with `-pg`, so `memset` does not
appear, and the `mcount` instrumentation cost and any kernel time (page
faults on the 27 MB rgb buffer, say) are not sampled either. gprof therefore
cannot say how the missing two thirds splits between `memset` and the
instrumentation.

What is confirmed: `objdump -d build-rel/bench-runs` (the Release build)
shows `vgaframe_push` makes `call` instructions to `vgaframe_timing_push`,
`vgaframe_colour` and `memset@plt`, so in the optimised build `memset` is a real libc call
through the PLT, not inlined (gprof's call counts show the colour call runs
on 73174930 of 73483645 pushes, the rest being outside a frame). `vgaframe_colour` is also a call, not inlined.

Of the sampled time, the learner (`vgaframe_timing_push`) is only 19%.
`vgaframe_push`'s own body and `vgaframe_colour` take 55% between them, so the
sync-level branch chain and the colour lookup matter more than the learner.

The per-push steps, read from `vgaframe_push` in `src/frame/frame.c`: two
signal-map bit extractions, the learner update, the `fram_active`/`r == 1/2/3`
branch chain, `vgaframe_colour`, a `memset` of the run, and the `cover[y]`
store.

**Hypotheses (not measured):** the unattributed 67% is mostly `memset` call
overhead plus `mcount`; levers that might help are a fast path for runs
without a sync change, a precomputed per-sample colour table, a batch entry
point for a run array, and a store in place of the 1-byte `memset`. None has
been tried.

## Caveats

- `busy` is a worst case: real simulated projects have fewer runs per clock.
  `busy` has 0.73 runs/clock; `bars` 0.076; `static` 0.0048. Interpolating
  at ~62 to 141 ns/run, a project's cost is roughly runs x ~100 ns.
- The replay repeats one frame's runs, so the input is cache-warm. A real
  stream reads its input once; the effect was not measured.
- Single thread, shared host; numbers are not isolated.

## After the fast path (M10 Task 7a)

Code: vgacap branch `m10-format-v2`, `a26c942` plus the bench tool
cherry-picked (`1ca169d`, `e8f60c0`) as the before, and `ead2e39` as the after.
Behaviour is unchanged: `test_frame_fastpath` runs the three profiles and a
random glitchy stream (five signal maps, FRAM windows included; also forced
modes, buffers narrower and shorter than the line and frame, and a timing no
table mode matches, auto-cropped) through both the new `vgaframe_push` and the
`a26c942` code kept in `tests/fastpath_ref/`. It compares state and emitted
frames after every push, and the raw, rgb and cover buffers byte for byte
every 4096 pushes and at flush. `frames=3570` is the same before and after on every run.

Method as above (Release `build-rel/`, `bench-runs`), but measured on
2026-11-25 at load average 25.6 to 27.7 (about 0.3 per core), the before and
after binaries interleaved, 3 runs each at 1.5e9 clocks, median reported.

**The host load matters more than it seemed.** Task 2's own code (`18b3468`),
rebuilt and run at this lower load, gives busy 18.57, bars 4.54, static 2.83
ns/clock (150e6 clocks, median of 3), against the 45.67 / 10.66 / 5.00 recorded
above at load 95 to 116. So the before figures below come from the same
conditions as the after figures, not from the table above.

| profile | Task 2 (load ~95) | before, today (3 runs) | after, today (3 runs) | before median | after median | speed-up |
|---|---|---|---|---|---|---|
| busy   | 45.673 | 18.473, 18.435, 18.508 | 6.836, 6.804, 6.705 | 18.473 | **6.804** | 2.7x |
| bars   | 10.657 | 4.602, 4.490, 4.484    | 1.402, 1.424, 1.531 | 4.490  | **1.424** | 3.2x |
| static | 4.997  | 2.801, 2.910, 2.810    | 0.620, 0.639, 0.627 | 2.810  | **0.627** | 4.5x |

ns per run, after: busy 9.26, bars 18.8, static 131.

Each change, `bench-runs --clocks 150000000`, median of 3, load 25 to 45:

| change (vgacap commit) | busy | bars | static |
|---|---|---|---|
| before (`e8f60c0`) | 19.373 | 4.827 | 3.054 |
| per-sample pixel table instead of `vgaframe_colour` (`3b32bd7`) | 14.582 | 4.235 | 2.863 |
| no-edge inline `vgaframe_timing_push_no_edge`, one copy of the additions (`c6fb755`) | 13.770 | 3.984 | 2.816 |
| clear only raw's dirty box after a frame, not 4 MB (`883bfa8`) | 12.195 | 3.117 | 2.138 |
| crop through a 256-entry rgb table (`d087948`) | 10.782 | 1.592 | 0.602 |
| fast path kept small, the rest in `push_rest` (`ecb2ef4`) | 9.588 | 1.490 | 0.618 |
| a one-clock run is one store, not a `memset` call (`ead2e39`) | 6.849 | 1.525 | 0.640 |

Rejected: storing runs of 1 to 8 clocks with a loop instead of `memset` was
no faster after the pixel table (14.58 to 14.88) and slower after the split
(10.69 to 11.23, A/B). The two largest wins came from measurement, not from
the gprof hypotheses above: with emit's 4 MB raw clear removed outright busy
fell from 13.8 to 9.2, and with the crop loop removed from 12.2 to 10.1.

gprof of the after build (`-pg`, busy, 150e6 clocks, load 30): 1.06 s of
samples out of 2.60 s wall. `vgaframe_push` 72.7%, the replay loop in `main`
20.8%, `emit` 5.7%, `push_rest` 0.9%. The learner's slow path runs only on
the 375000 hsync edges and no longer shows.

### Against the 11 ns/clock budget

At today's load the after figures are all inside it: busy 6.8 ns/clock leaves
4.2 for the samplers, bars 1.4 leaves 9.6, static 0.6 leaves 10.4.

**Concern, not measured:** Task 2's code ran 2.46x slower at load 95 to 116
than at load 26 (45.67 against 18.57). If the after build slowed by the same
factor at that load, busy would be about 16.7 ns/clock, over the budget; bars
(3.5) and static (1.5) would stay inside it. Whether the slowdown is
proportional was not measured; the cause is presumably hyperthread siblings
and shared cache under a full host.

## vgacap-sample on a 1.5e9-clock busy trace (M10 Task 16)

`bench-runs --profile busy --clocks 1500000000 --write-trace tmp/busy.trace.zst`
(vgacap `m10-sample-tool` 9ff2019, Release build) wrote the busy stream as a
tt-um-43 trace: 3e9 samples, 462 blocks, 16,035,812 bytes, in 15.0 s
(10.0 ns/clock). `vgacap-sample` then read it in one pass
(`trace_passes=1 blocks_decoded=462`), host load average 30 to 52 (of 88):

| run | wall s | ns/clock |
|---|---|---|
| both samplers (the default) | 131.18 | 87.5 |
| `--sampler tb-v1` | 93.16 | 62.1 |
| `--sampler centre-v1` | 103.28 | 68.9 |
| `vgacap-calib-dump` (trace read, calibration, frame clock only) | 66.67 | 44.4 |

Each sampler wrote 3,566 frames, one distinct (the busy picture is static);
tb-v1 and centre-v1 stored the same picture (same SHA-256). Peak RSS 64 MB.

### Against the 11 ns/clock budget

The budget is for all post-simulation work; vgacap-sample takes 87.5
ns/clock, 8x over it. By subtraction (not profiled): reading the trace with
the calibration and the frame clock is about 44 ns/clock, tb-v1 about 18,
centre-v1 (libvgaframe plus the pick) about 25. The read path is the largest
part: busy has one run per clock (1.5e9 callbacks from
`vgacap_trace_read`, each also fed to the frame clock), so the per-run cost
of the stream decoder and the callback chain dominates; libvgaframe itself
measured 6.8 ns/clock above. Levers (hypotheses, unmeasured): a batched run
reader (arrays of runs per block instead of a callback per run), a cheaper
frame-clock push for runs that cannot end a vsync pulse, and decoding blocks
on a second thread.
