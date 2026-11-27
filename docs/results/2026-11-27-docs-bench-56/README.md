# Bench run of vgacap docs PR #56 on fpga-1 and tt09's Pi

Date: 2026-11-27 (UTC). Code: vgacap 524e0ad, b6fa47b and d19b87d (pass 1) and ae02e33 (pass 2), branch
`docs-final-fixes` ([mithro/vgacap#56](https://github.com/mithro/vgacap/pull/56)). Nothing was flashed.

Pass 1 ran these pages on the bench boards:

- [`python/ttcap/how-to-capture-welland-pi.md`](https://github.com/mithro/vgacap/blob/b6fa47b/python/ttcap/how-to-capture-welland-pi.md),
  steps 1 to 7 and its Check.
- The render in step 4 of [`firmware/how-to-capture.md`](https://github.com/mithro/vgacap/blob/b6fa47b/firmware/how-to-capture.md)
  and [`mpy/how-to-capture.md`](https://github.com/mithro/vgacap/blob/b6fa47b/mpy/how-to-capture.md).
- The render in the Check of [`firmware/how-to-select-asic-project.md`](https://github.com/mithro/vgacap/blob/d19b87d/firmware/how-to-select-asic-project.md).

Of the pages run, only the step ranges in one "If it fails" row of `firmware/how-to-capture.md` changed between
them ([`pages-cb3a4a6-to-524e0ad.log`](pages-cb3a4a6-to-524e0ad.log),
[`pages-524e0ad-to-b6fa47b.log`](pages-524e0ad-to-b6fa47b.log),
[`pages-b6fa47b-to-d19b87d.log`](pages-b6fa47b-to-d19b87d.log)).

Pass 2 ran the steps that changed after pass 1, at ae02e33:

- step 2 of [`python/ttcap/how-to-run-on-raspberry-pi.md`](https://github.com/mithro/vgacap/blob/ae02e33/python/ttcap/how-to-run-on-raspberry-pi.md),
  which now copies `uvx`;
- the enable note of [`how-to-capture-welland-pi.md`](https://github.com/mithro/vgacap/blob/ae02e33/python/ttcap/how-to-capture-welland-pi.md),
  then its steps 3 to 7;
- step 4 of [`firmware/how-to-capture.md`](https://github.com/mithro/vgacap/blob/ae02e33/firmware/how-to-capture.md)
  and [`mpy/how-to-capture.md`](https://github.com/mithro/vgacap/blob/ae02e33/mpy/how-to-capture.md), on a workstation.

## Boards

| Board | Pi | Pi model | Userland | USB serial | MicroPython | SDK |
|---|---|---|---|---|---|---|
| fpga-1 | pi-sw2-p34 | not recorded | 32-bit | `4df39a7a6856f86f` | 970468103d | 3.1.1 |
| tt09 | pi-sw2-p10 | Raspberry Pi 3 Model B Plus Rev 1.4 | 32-bit | `3b0880b48ee5c388` | not read | not read |

The tt09 Pi's model and userland are in [`run1-tt09pi-baseline.log`](run1-tt09pi-baseline.log). fpga-1's
userland is in [`run1-fpga1-setup-524e0ad.log`](run1-fpga1-setup-524e0ad.log). fpga-1's firmware is in the
restart output of [`run1-welland-pi-steps-b6fa47b.log`](run1-welland-pi-steps-b6fa47b.log).

On tt09's Pi only the home directory was used. The board's USB device and its bridge were not touched.

## Claims

| Claim | Board id | Taken | Released |
|---|---|---|---|
| `c-d0_fbdperSJF` | `welland:pi-sw2-p34` | 03:39:29Z | not logged |
| `c-iBgHwSefhKlz` | `welland:pi-sw2-p34` | 05:33:22Z | 05:38:32Z |
| `c-eerM7kHr3CzC` | `welland:pi-sw2-p10` | 05:40:17Z | 05:41:38Z |
| `c-umRp-EySdgNp` | `tinytapeout:tt-3b0880b48ee5c388` | 05:42:16Z | 05:46:15Z |
| `c-u_zA2pL29hIw` | `welland:pi-sw2-p34` | 05:55:31Z | 05:58:27Z |

The claim IDs and times come from the broker's replies. These were copied verbatim into
[`broker-replies.log`](broker-replies.log) after the run; no script logged them at the time.

- `c-d0_fbdperSJF` was released by the coordinating session after a usage-limit stop, and no reply records when.
- `welland:pi-sw2-p10`'s in-use check returned `unknown`, because its welland page is a 404.
- The two tt09 claims gave an override reason: Tim's 2026-11-27 approval to use any fpgas.online board for the vgacap docs bench runs.
- `connect` refused `welland:pi-sw2-p10` because of the same 404. The Pi had to be claimed as `tinytapeout:tt-3b0880b48ee5c388`.

The broker CLI's claim lists are in these logs:

- [`claims-cli-run1-before.log`](claims-cli-run1-before.log)
- [`claims-cli-run1b-before.log`](claims-cli-run1b-before.log)
- [`claims-cli-run2-before.log`](claims-cli-run2-before.log)
- [`claims-cli-run1-after.log`](claims-cli-run1-after.log)

The only claim left afterwards was another session's, on fpga-4.

## Setup

| Run | Pi | Commit | Log |
|---|---|---|---|
| Pass 1, first session | fpga-1's Pi | 524e0ad | [`run1-fpga1-setup-524e0ad.log`](run1-fpga1-setup-524e0ad.log) |
| Pass 1, second session | fpga-1's Pi | b6fa47b | [`run1-fpga1-setup-b6fa47b.log`](run1-fpga1-setup-b6fa47b.log) |
| Pass 1 | tt09's Pi | d19b87d | [`run1-tt09pi-setup-d19b87d.log`](run1-tt09pi-setup-d19b87d.log) |
| Pass 2 | fpga-1's Pi | ae02e33 | [`run2-step2-uvx.log`](run2-step2-uvx.log) |
| Pass 2 | big-storage | ae02e33 | [`run2-workstation-checkout.log`](run2-workstation-checkout.log) |

Each Pi checkout was a clone of mithro/vgacap, checked out at `docs-final-fixes`. Setup used steps 1 to 3 of
`how-to-run-on-raspberry-pi.md` at that commit.

## Results

| Page | Pass | Board | Result | Log |
|---|---|---|---|---|
| `how-to-capture-welland-pi.md` steps 1 to 7 | 1 | fpga-1 | passed as written | [`run1-welland-pi-steps-524e0ad.log`](run1-welland-pi-steps-524e0ad.log) |
| `how-to-capture-welland-pi.md` steps 1 to 7 | 1 | fpga-1 | passed as written | [`run1-welland-pi-steps-b6fa47b.log`](run1-welland-pi-steps-b6fa47b.log) |
| render of the idle-display capture | 1 | fpga-1's Pi | stop | [`run1-fpga1-cmake-render-idle.log`](run1-fpga1-cmake-render-idle.log) |
| welland-pi step 4 with `--project tt_um_vga_pattern` | 1 | fpga-1 | refused | [`run1-project-refused.log`](run1-project-refused.log) |
| firmware and mpy step 4 on the Pi | 1 | fpga-1's Pi | stop | [`run1-vga-capture-overrun.log`](run1-vga-capture-overrun.log) |
| `uv sync --extra synth`, then `ttcap png` | 1 | fpga-1's Pi | passed | [`run1-fpga1-synth-pillow.log`](run1-fpga1-synth-pillow.log) |
| asic-select Check render on the Pi | 1 | tt09's Pi | stop | [`run1-tt09pi-cmake-render.log`](run1-tt09pi-cmake-render.log) |
| `uv sync --extra synth` | 1 | tt09's Pi | stopped by watchdog | [`run1-tt09pi-synth-watchdog.log`](run1-tt09pi-synth-watchdog.log) |
| `how-to-run-on-raspberry-pi.md` step 2 | 2 | fpga-1's Pi | passed as written | [`run2-step2-uvx.log`](run2-step2-uvx.log) |
| welland-pi enable note, then steps 3 to 7 | 2 | fpga-1 | passed as written | [`run2-welland-pi-enable-steps.log`](run2-welland-pi-enable-steps.log) |
| firmware and mpy step 4 on a workstation | 2 | big-storage | passed as written | [`run2-workstation-render.log`](run2-workstation-render.log) |

Notes on the results:

- **Pass 1, welland-pi step 4:** the clean run wrote 1902002 bytes in 4.046 s with `overruns=0 dropped=0 rxstall=0`.
- **Idle-display render:** `ttcap png` printed `frames=0` and `no frame decoded`.
- **`--project` refusal:** ttcap said `not a shuttle entry on this board`, and that the design has to be enabled through the board's daemon first.
- **Render on fpga-1's Pi:** it decoded 2 frames, then stopped with `Pillow is needed to write PNGs: uv sync --extra synth`. After that sync it printed `wrote 2 png(s)`.
- **Render on tt09's Pi:**
  - cmake installed and built.
  - `ttcap png` stopped on Pillow, as on fpga-1's Pi.
  - `uv sync --extra synth` filled the root filesystem, so a watchdog stopped it.
- **Pass 1 enable step:** the VGA capture needed a step the page did not yet have. It was `curl -s -X POST localhost:8765/designs/tt_um_vga_pattern/enable`, at 0 clients, before step 3. Pass 2 ran the note the page now has for this.
- **Pass 2, welland-pi:** passed as written; step 4 reported `overruns=1 dropped=16384`.
- **Pass 2, workstation:**
  - It printed `frames=3 glitches_total=0` and `wrote 3 png(s)`.
  - The colour bars are in [`run2-frame-0000.png`](run2-frame-0000.png).
  - The workstation copied `bench.vgacap`, the name the welland-pi page writes. The page's example names `frame.vgacap`.

The pages' example board is fpga-4. Its `/designs` lists `tt_um_vga_pattern` as a demo design
([`run2-fpga4-designs.log`](run2-fpga4-designs.log)). It was read through
`https://tinytapeout.fpgas.online/api/board/fpga-4/designs`, without disturbing the board.

## Measurements

### Step 6 to `loaded`

| Run | Commit | Seconds | Log |
|---|---|---|---|
| Pass 1, steps 1 to 7 | 524e0ad | 72 | [`run1-welland-pi-steps-524e0ad.log`](run1-welland-pi-steps-524e0ad.log) |
| Pass 1, `--project` refused | 524e0ad | 71 | [`run1-project-refused.log`](run1-project-refused.log) |
| Pass 1, VGA capture with overrun | 524e0ad | 72 | [`run1-vga-capture-overrun.log`](run1-vga-capture-overrun.log) |
| Pass 1, clean run | b6fa47b | 72 | [`run1-welland-pi-steps-b6fa47b.log`](run1-welland-pi-steps-b6fa47b.log) |
| Pass 1, small capture | b6fa47b | 72 | [`run1-small-capture.log`](run1-small-capture.log) |
| Pass 2 | ae02e33 | 72 | [`run2-welland-pi-enable-steps.log`](run2-welland-pi-enable-steps.log) |

### `"clients": 1` during step 7

| Run | Poll at | Log |
|---|---|---|
| Pass 1, steps 1 to 7 | 67 s | [`run1-welland-pi-steps-524e0ad.log`](run1-welland-pi-steps-524e0ad.log) |
| Pass 1, `--project` refused | 66 s | [`run1-project-refused.log`](run1-project-refused.log) |
| Pass 1, clean run | 67 s | [`run1-welland-pi-steps-b6fa47b.log`](run1-welland-pi-steps-b6fa47b.log) |
| Pass 2 | 67 s | [`run2-welland-pi-enable-steps.log`](run2-welland-pi-enable-steps.log) |

In each, the next poll showed `"clients": 0` and `loaded`. The other two runs logged no per-poll lines.

### Build and render times

| What | Machine | Seconds | Log |
|---|---|---|---|
| `uvx --from cmake` configure with cmake install | fpga-1's Pi | about 5.2 | [`run1-fpga1-cmake-render-idle.log`](run1-fpga1-cmake-render-idle.log) |
| `vgacap-frames` build | fpga-1's Pi | 3.4 | [`run1-fpga1-cmake-render-idle.log`](run1-fpga1-cmake-render-idle.log) |
| `uv sync --extra synth` | fpga-1's Pi | 633.9 | [`run1-fpga1-synth-pillow.log`](run1-fpga1-synth-pillow.log) |
| `uvx --from cmake` configure with cmake install | tt09's Pi | 15.0 | [`run1-tt09pi-cmake-render.log`](run1-tt09pi-cmake-render.log) |
| `vgacap-frames` build | tt09's Pi | 7.8 | [`run1-tt09pi-cmake-render.log`](run1-tt09pi-cmake-render.log) |
| `uvx --from cmake cmake --version` | fpga-1's Pi | 0.72 | [`run2-welland-pi-enable-steps.log`](run2-welland-pi-enable-steps.log) |
| `uv sync` | big-storage | 4.2 | [`run2-workstation-render.log`](run2-workstation-render.log) |
| cmake configure | big-storage | 2.7 | [`run2-workstation-render.log`](run2-workstation-render.log) |
| `vgacap-frames` build | big-storage | 4.8 | [`run2-workstation-render.log`](run2-workstation-render.log) |
| `ttcap png` | big-storage | 1.4 | [`run2-workstation-render.log`](run2-workstation-render.log) |

- The fpga-1 configure time is approximate: its timing lines interleave with the output in the log.
- On fpga-1's Pi, `uv sync --extra synth` built numpy 2.4.6 and Pillow 12.3.0 from source in 10 min 33 s.
- The fpga-1 Pi installed cmake 4.4.5.

### tt09's Pi and `uv sync --extra synth`

| Time | Root free | MemAvailable |
|---|---|---|
| 0 s | 221 MB | 494 MB |
| 11 s | 84 MB | 337 MB |
| 21 s | 33 MB | 245 MB |

These are from [`run1-tt09pi-synth-watchdog.log`](run1-tt09pi-synth-watchdog.log). The watchdog stopped uv at
21 s, while uv was at `Building pillow` and `Building numpy`. The root filesystem is 459 MB, with its upper layer on
tmpfs ([`run1-tt09pi-mounts.log`](run1-tt09pi-mounts.log)). It shares the Pi's RAM, `Mem: 916` in
[`run1-tt09pi-cmake-render.log`](run1-tt09pi-cmake-render.log).

### The uvx 0.13.1 cache

In pass 1, step 2 copied only `uv`, so `uvx` was `/usr/local/bin/uvx` 0.13.1. It downloaded cmake again
(`Downloading cmake (26.1MiB)` in [`run1-fpga1-cmake-render-idle.log`](run1-fpga1-cmake-render-idle.log)).
uv 0.10.8's `wheels-v6` already held cmake 4.4.5 ([`run1-fpga1-uv-cache-links.log`](run1-fpga1-uv-cache-links.log)).
uvx 0.13.1 keeps its own buckets: `wheels-v7`, `simple-v26` and `sdists-v10` ([`run1-fpga1-uv-cache-v7.log`](run1-fpga1-uv-cache-v7.log)).
With `uvx` copied in pass 2, `uvx` was 0.10.8 and used the cached cmake.

### 500 kHz with `tt_um_vga_pattern`

| Run | Seconds | Overruns | Dropped | Log |
|---|---|---|---|---|
| Pass 1, 4 s | 4.017 | 2 | 32768 | [`run1-vga-capture-overrun.log`](run1-vga-capture-overrun.log) |
| Pass 2, 4 s | 4.036 | 1 | 16384 | [`run2-welland-pi-enable-steps.log`](run2-welland-pi-enable-steps.log) |
| Pass 1, 2 s | 2.037 | 0 | 0 | [`run1-small-capture.log`](run1-small-capture.log) |

The welland-pi step 4 stream at 500 kHz on fpga-1 overran in both 4-second runs with the design enabled. A
2-second run was clean. The two 4-second captures of the idle display at 500 kHz were clean
([`run1-welland-pi-steps-524e0ad.log`](run1-welland-pi-steps-524e0ad.log),
[`run1-welland-pi-steps-b6fa47b.log`](run1-welland-pi-steps-b6fa47b.log)).

## Restore

### Board state

| Board | When | `clients` | `idle_display` | Enabled | Status file | Designs log |
|---|---|---|---|---|---|---|
| fpga-1 | before pass 1 | 0 | `loaded` | `idle_display` | [`status-run1-before-fpga1.json`](status-run1-before-fpga1.json) | [`run1-fpga1-designs-before.log`](run1-fpga1-designs-before.log) |
| fpga-1 | after pass 1 | 0 | `loaded` | `idle_display` | [`status-run1-after-fpga1.json`](status-run1-after-fpga1.json) | [`run1-fpga1-designs-after.log`](run1-fpga1-designs-after.log) |
| fpga-1 | before pass 2 | 0 | `loaded` | not read | [`status-run2-before-fpga1.json`](status-run2-before-fpga1.json) | none |
| fpga-1 | after pass 2 | 0 | `loaded` | `idle_display` | [`status-run2-after-fpga1.json`](status-run2-after-fpga1.json) | [`run2-fpga1-cleanup.log`](run2-fpga1-cleanup.log) |
| tt09 | before | 0 | `not an fpga board` | not read | [`status-run1-before-tt09.json`](status-run1-before-tt09.json) | none |
| tt09 | after | 0 | `not an fpga board` | not read | [`status-run1-after-tt09.json`](status-run1-after-tt09.json) | none |

- tt09's `safe_start` read `set: clock stopped ...` before and after.
- fpga-1's `safe_start` read `not a chip board` throughout.
- Every restart with logged output booted MicroPython 970468103d with SDK 3.1.1, into `FPGA:tt_um_factory_test`. The bridge then loaded the idle display.
- `run1-fpga1-designs-after.log` was read after the second pass-1 session. The coordinating session restored fpga-1 after the first, and did not log it here.

### Clean-up

Each Pi lost `~/vgacap`, the uv tarball and its directory, `~/.local/bin` and the uv cache entries the run added.

| Pi | After | Log |
|---|---|---|
| fpga-1's Pi, pass 1, first removal | 81M, `wheels-v7` left | [`run1-fpga1-cleanup.log`](run1-fpga1-cleanup.log) |
| fpga-1's Pi, pass 1, buckets found | `wheels-v7`, `sdists-v10`, `simple-v26` | [`run1-fpga1-uv-cache-v7.log`](run1-fpga1-uv-cache-v7.log) |
| fpga-1's Pi, pass 1, final | 80M | [`run1-fpga1-uv-cache-final.log`](run1-fpga1-uv-cache-final.log) |
| tt09's Pi | `~/.cache` 5.9M, root 425 MB free | [`run1-tt09pi-cleanup.log`](run1-tt09pi-cleanup.log) |
| fpga-1's Pi, pass 2 | 80M | [`run2-fpga1-cleanup.log`](run2-fpga1-cleanup.log) |

- The first fpga-1 removal ran under `set -x`, so its commands are in the log.
- That removal missed uvx 0.13.1's three buckets.
- The `rm` that removed them was not logged; only its output is in `run1-fpga1-uv-cache-final.log`.
- 80M is what `~/.cache/uv` held before the run.
- After the first pass-1 session, the coordinating session cleaned fpga-1's Pi. It did not log that clean-up here.
