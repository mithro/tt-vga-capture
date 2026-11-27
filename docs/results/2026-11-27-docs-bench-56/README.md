# Bench run of vgacap docs PR #56 on fpga-1 and tt09's Pi

Date: 2026-11-27 (UTC). Pages from [mithro/vgacap#56](https://github.com/mithro/vgacap/pull/56), branch
`docs-final-fixes`. Nothing was flashed. There were two passes:

- **Pass 1** ran `python/ttcap/how-to-capture-welland-pi.md` steps 1 to 7 and its Check, and the render (step 4
  of `firmware/how-to-capture.md` and `mpy/how-to-capture.md`, and the Check of
  `firmware/how-to-select-asic-project.md`) on the bench Pis. Commits 524e0ad, b6fa47b and d19b87d. Only the
  step ranges in one "If it fails" row of `firmware/how-to-capture.md` changed between them.
- **Pass 2** ran the steps changed after pass 1, at ae02e33:
  - step 2 of `python/ttcap/how-to-run-on-raspberry-pi.md`, which now copies `uvx`;
  - the enable note of the welland-pi page, then its steps 3 to 7;
  - step 4 of the firmware and mpy capture pages, on a workstation.

## Boards

| Board | Pi | Pi model | Userland | USB serial | Firmware | Claims |
|---|---|---|---|---|---|---|
| fpga-1 | pi-sw2-p34 | Raspberry Pi 4 | 32-bit | `4df39a7a6856f86f` | MicroPython 970468103d, SDK 3.1.1 | `c-d0_fbdperSJF`, `c-iBgHwSefhKlz`, `c-u_zA2pL29hIw` |
| tt09 | pi-sw2-p10 | Raspberry Pi 3 Model B Plus Rev 1.4 | 32-bit | `3b0880b48ee5c388` | not touched | `c-umRp-EySdgNp` |

- **Claims:** all were taken through the fpgas.online broker, and all were released.
- **tt09's Pi:**
  - The claim used an override, under Tim's 2026-11-27 approval to use any fpgas.online board for the vgacap docs bench runs.
  - Claiming `welland:pi-sw2-p10` worked, but connecting failed because its welland page is a 404. The Pi had to be claimed as `tinytapeout:tt-3b0880b48ee5c388`.
  - Only the home directory on tt09's Pi was used. The board's USB device and bridge were not touched.
  - Its bridge process (PID 1274) ran through the whole session.

## Results

| Page | Pass | Board | Result | Logs |
|---|---|---|---|---|
| `how-to-capture-welland-pi.md` steps 1 to 7 and Check | 1 | fpga-1 | Passed as written. Step 4: 1902002 bytes in 4.046 s, `overruns=0 dropped=0 rxstall=0` | `run1-welland-pi-steps-524e0ad.log`, `run1-welland-pi-steps-b6fa47b.log` |
| `how-to-capture-welland-pi.md`, capture of the idle display | 1 | fpga-1 | Stop: `ttcap png` printed `frames=0`, `no frame decoded` | `run1-fpga1-cmake-render-idle.log` |
| `how-to-capture-welland-pi.md` step 4 with `--project tt_um_vga_pattern` | 1 | fpga-1 | Refused: `not a shuttle entry on this board ... enabled through the board's daemon first` | `run1-project-refused.log` |
| Firmware and mpy step 4, render on the Pi | 1 | fpga-1 | Stop: `Pillow is needed to write PNGs: uv sync --extra synth`. After that sync, `wrote 2 png(s)` | `run1-vga-capture-overrun.log`, `run1-fpga1-synth-pillow.log` |
| `how-to-select-asic-project.md` Check, render on the Pi | 1 | tt09's Pi | cmake installed and built. `ttcap png` stopped on Pillow. `uv sync --extra synth` filled the root filesystem | `run1-tt09pi-cmake-render.log`, `run1-tt09pi-synth-watchdog.log` |
| `how-to-run-on-raspberry-pi.md` step 2, with `uvx` | 2 | fpga-1's Pi | Passed as written: `uv 0.10.8`, and `uvx` resolves to `~/.local/bin/uvx` 0.10.8 | `run2-step2-uvx.log` |
| `how-to-capture-welland-pi.md` enable note, then steps 3 to 7 | 2 | fpga-1 | Passed as written | `run2-welland-pi-enable-steps.log` |
| Firmware and mpy step 4 on a workstation | 2 | big-storage | Passed as written: `frames=3 glitches_total=0`, `wrote 3 png(s)`. The colour bars are in `run2-frame-0000.png` | `run2-workstation-render.log` |

In pass 1, the welland-pi capture with `tt_um_vga_pattern` enabled through the bridge needed a step the page did not
yet have: `curl -s -X POST localhost:8765/designs/tt_um_vga_pattern/enable` at 0 clients, before step 3. Pass 2 ran
the note the page now has for this.

In pass 2 the workstation step 4 copied `bench.vgacap`, the name the welland-pi page writes, where the page's
example names `frame.vgacap`.

The pages' example board is fpga-4. Its bridge's `/designs`, read through
`https://tinytapeout.fpgas.online/api/board/fpga-4/designs` without disturbing the board, lists
`tt_um_vga_pattern` as a demo design (`run2-fpga4-designs.log`).

## Measurements

| What | Board | Value | Log |
|---|---|---|---|
| Step 6 to `idle_display` `"state": "loaded"` | fpga-1 | 72 s in the clean run; 72 s, 71 s, 72 s, 72 s and 72 s in the other runs | `run1-welland-pi-steps-b6fa47b.log`, `run2-welland-pi-enable-steps.log` |
| `"clients": 1` during step 7 | fpga-1 | one poll at 67 s in three runs; the next poll showed 0 and `loaded` | `run2-welland-pi-enable-steps.log` |
| `uvx --from cmake` configure, including the cmake 4.4.5 install | fpga-1's Pi | about 5.2 s (timing lines interleaved in the log) | `run1-fpga1-cmake-render-idle.log` |
| `vgacap-frames` build | fpga-1's Pi | 3.4 s | `run1-fpga1-cmake-render-idle.log` |
| `uvx --from cmake` configure, including the cmake 4.4.5 install | tt09's Pi | 15.0 s | `run1-tt09pi-cmake-render.log` |
| `vgacap-frames` build | tt09's Pi | 7.8 s | `run1-tt09pi-cmake-render.log` |
| `uv sync --extra synth`: numpy 2.4.6 and Pillow 12.3.0 built from source | fpga-1's Pi | 10 min 33 s | `run1-fpga1-synth-pillow.log` |
| `uv sync --extra synth` | tt09's Pi | root went from 221 MB to 33 MB free in 21 s, before any compiling; a watchdog stopped it | `run1-tt09pi-synth-watchdog.log` |
| Root filesystem | tt09's Pi | 459 MB, upper layer on tmpfs, so it shares the Pi's 916 MB RAM | `run1-tt09pi-mounts.log` |
| `uvx --from cmake cmake --version`, step 2 with `uvx` copied | fpga-1's Pi | 0.72 s, no download | `run2-welland-pi-enable-steps.log` |
| Workstation `uv sync`, configure, build and `ttcap png` | big-storage | 4.2 s, 2.7 s, 4.8 s and 1.4 s | `run2-workstation-render.log` |

**The uvx 0.13.1 cache.** In pass 1, step 2 copied only `uv`, so `uvx` was `/usr/local/bin/uvx` 0.13.1. It keeps
its own cache buckets (`wheels-v7`, `simple-v26`, `sdists-v10`), so it downloaded cmake again (26.1 MiB) although
uv 0.10.8's `wheels-v6` already held cmake 4.4.5. With `uvx` copied (pass 2), `uvx` is 0.10.8 and used the cached
cmake.

**500 kHz with `tt_um_vga_pattern`.** The welland-pi step 4 stream at 500 kHz on fpga-1 overran in two of three
4-second runs with the design enabled:

| Run | Seconds | Overruns | Dropped | Log |
|---|---|---|---|---|
| Pass 1, 4 s | 4.017 | 2 | 32768 | `run1-vga-capture-overrun.log` |
| Pass 2, 4 s | 4.036 | 1 | 16384 | `run2-welland-pi-enable-steps.log` |
| Pass 1, 2 s | 2.037 | 0 | 0 | `run1-small-capture.log` |

The two 4-second captures of the idle display at 500 kHz were clean (`run1-welland-pi-steps-524e0ad.log`, `run1-welland-pi-steps-b6fa47b.log`).

## Board state before and after

| Board | When | `clients` | `idle_display` | `safe_start` | Enabled | Files |
|---|---|---|---|---|---|---|
| fpga-1 | before pass 1 | 0 | `loaded` | `not a chip board` | `idle_display` | `status-run1-before-fpga1.json` |
| fpga-1 | after pass 1 | 0 | `loaded` | `not a chip board` | `idle_display` | `status-run1-after-fpga1.json` |
| fpga-1 | before pass 2 | 0 | `loaded` | `not a chip board` | `idle_display` | `status-run2-before-fpga1.json` |
| fpga-1 | after pass 2 | 0 | `loaded` | `not a chip board` | `idle_display` | `status-run2-after-fpga1.json`, `run2-fpga1-cleanup.log` |
| tt09 | before | 0 | `not an fpga board` | `set: clock stopped ...` | not read | `status-run1-before-tt09.json` |
| tt09 | after | 0 | `not an fpga board` | `set: clock stopped ...` | not read | `status-run1-after-tt09.json` |

fpga-1 ran its stock firmware throughout. Each restart booted MicroPython 970468103d with SDK 3.1.1 into
`FPGA:tt_um_factory_test`, and the bridge then loaded the idle display.

**Clean-up on each Pi:**
- Removed: `~/vgacap`, the uv tarball and its directory, `~/.local/bin`, and every uv cache entry the run added.
- `~/.cache/uv` was back to its size and entries from before the run: 80M on fpga-1's Pi and 5.9M on tt09's Pi.
- On tt09's Pi, the root filesystem was back to 425 MB free.
- Logs: `run1-fpga1-cleanup.log`, `run1-tt09pi-cleanup.log`, `run2-fpga1-cleanup.log`.
