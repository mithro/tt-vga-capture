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

Spread is large for `bars` and `static` (first run 20-35% slower than the
others; likely the other tenants on the host, or a cold cache/frequency state
for the first pass). Treat `bars` as 8.8 to 10.7 ns/clock.

A 1.5e8-clock pilot gave busy 48.9, bars 10.8, static 6.5 ns/clock. I estimated
the 1.5e9 runs from it at about 50 minutes total, but that was a 10x arithmetic
error on my part: 10 x 7 s is 70 s per busy run, and the nine runs took 4.6
minutes in all.

## Against the 11 ns/clock budget

- `static`: 5.0 ns/clock, leaves about 6.0 ns/clock (55%) for the samplers.
- `bars`: 10.7 ns/clock, leaves about 0.3 ns/clock. The best run (8.8) left 2.2.
  Effectively the whole budget.
- `busy`: 45.7 ns/clock, which is **34.7 ns/clock over** the budget (4.2x it).
  Nothing is left for samplers, and libvgaframe alone would cost about
  21% of a 220 ns/clock simulation, not 5%. At 1.5e9 clocks that is 68 s of
  libvgaframe time per project.

Cost is dominated by the per-run work, not per clock: about 62 ns/run on busy
(one clock per run), 141 ns/run on bars, and roughly 1 us/run on static, where
each run is a long `memset` plus a full line of idle time.

## What costs it (no profile)

`perf` is not installed on big-storage (`perf: command not found`), so there is
no `perf record`. From reading `vgaframe_push` (`src/frame/frame.c`) and
`vgaframe_timing_push`, every call, even for a 1-clock run, does:

1. two signal-map bit extractions (hsync and vsync) with `VGACAP_SIG_ABSENT`
   checks;
2. a full `vgaframe_timing_push` learner update (edge detection, glitch filter,
   line/frame counters);
3. the chain of `fram_active`/`r == 3`/`r == 2`/`r == 1` branches, with
   `fram_anchor` and `resolved_mode()` checks;
4. `vgaframe_colour` via the signal map, then a `memset` of `n` bytes, which on a
   1-byte run is a libc call (not inlined) for one byte;
5. a `cover[y]` store and x advance.

This is a hypothesis, not a measurement. If the budget needs `busy` to fit, the
likely levers are: a batch entry point taking a run array, a fast path in the
learner for runs with no sync change (no edge, so only counters advance), a
per-sample precomputed colour/sync lookup, and replacing the 1-byte memset with
a store. Those need a profile (install `perf`, or use `valgrind --tool=callgrind`)
before choosing.

## Caveats

- `busy` is a worst case: real simulated projects have fewer runs per clock.
  `busy` has 0.73 runs/clock; `bars` 0.076; `static` 0.0048. Interpolating
  at ~62 to 141 ns/run, a project's cost is roughly runs x ~100 ns.
- The replay is cache-warm: one frame's runs (4 to 9 MB of buffers touched)
  are repeated. A real stream with unique runs also reads its input once.
- Single thread, shared host; numbers are not isolated.
