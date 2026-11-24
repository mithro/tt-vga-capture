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
