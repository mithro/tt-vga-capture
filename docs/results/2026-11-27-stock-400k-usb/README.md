# Stock firmware at 400 kHz over USB serial on fpga-1

Date: 2026-11-27 (UTC). Code: vgacap 59d37c0, branch `docs-final-fixes`
([mithro/vgacap#56](https://github.com/mithro/vgacap/pull/56)). Nothing was flashed.

No capture with the stock firmware at 400 kHz over USB serial had been run before. #56's pages recommend 400 kHz
on USB serial. These runs measure it with `tt_um_vga_pattern` enabled. All runs were on fpga-1's Pi, owning
`/dev/ttboard` with the bridge stopped.

## Board

| Board | Pi | Pi model | USB serial | Firmware |
|---|---|---|---|---|
| fpga-1 | pi-sw2-p34 | Raspberry Pi 4 Model B Rev 1.5 | `4df39a7a6856f86f` | stock |

The Pi model is in [`setup.log`](setup.log). The restart at the end of [`runs.log`](runs.log) booted
MicroPython 970468103d with SDK 3.1.1.

## Claim

| Claim | Board id | Taken | Released |
|---|---|---|---|
| `c-yQZrSYJbSzh6` | `welland:pi-sw2-p34` | 06:18:07Z | 06:20:44Z |

The claim was taken and released with the broker's CLI.

- [`claim.log`](claim.log) is its `claim --json` reply, with the in-use verdict `idle`.
- [`release.log`](release.log) is the `release` reply. It holds no time.
- The release time is that file's modification time, in [`mtimes.log`](mtimes.log) (16:50:44 +1030).
- [`pre.log`](pre.log) and [`claims-after.log`](claims-after.log) list the claims before and after. Only another session's claim on fpga-4 was live.

## Setup

[`setup.log`](setup.log) has the checkout and `uv sync` on the Pi.

- The checkout followed steps 1 to 3 of [`how-to-run-on-raspberry-pi.md`](https://github.com/mithro/vgacap/blob/59d37c0/python/ttcap/how-to-run-on-raspberry-pi.md), with `UV_NO_DEV=1` exported.
- [`setup.log`](setup.log) also shows the bridge journal for the 30 minutes before, which was empty.
- At the start of [`runs.log`](runs.log), `/health` showed `"clients": 0`, and the journal had no entries for the 10 minutes before.
- `tt_um_vga_pattern` was enabled at 0 clients, as the enable note of [`how-to-capture-welland-pi.md`](https://github.com/mithro/vgacap/blob/59d37c0/python/ttcap/how-to-capture-welland-pi.md) says. The bridge replied `{"enabled": "tt_um_vga_pattern", ...}`.
- The bridge was stopped once (step 3), and all five captures ran in a row.

## Runs

| Run | Command | Seconds | Bytes | Samples | Samples/s | Overruns | Dropped | rxstall |
|---|---|---|---|---|---|---|---|---|
| welland-pi step 4, run 1 | welland-pi step 4 | 4.049 | 1524894 | 1523712 | 376349 | 0 | 0 | 0 |
| welland-pi step 4, run 2 | welland-pi step 4 | 4.038 | 1524894 | 1523712 | 377321 | 0 | 0 | 0 |
| welland-pi step 4, run 3 | welland-pi step 4 | 4.041 | 1524894 | 1523712 | 377107 | 0 | 0 | 0 |
| stream step 2 | how-to-capture-stream step 2 | 4.039 | 1524894 | 1523712 | 377250 | 0 | 0 | 0 |
| 10 s capture | welland-pi step 4 with `--seconds 10` | 10.019 | 3918710 | 3915776 | 390827 | 0 | 0 | 0 |

All values are from [`runs.log`](runs.log). Every run reported `sysclk_hz=132000000` and exited 0.

- **welland-pi step 4:** run as written in [`how-to-capture-welland-pi.md`](https://github.com/mithro/vgacap/blob/59d37c0/python/ttcap/how-to-capture-welland-pi.md): `uv run --no-sync ttcap capture serial:/dev/ttboard --clock-hz 400000 --seconds 4 --out bench.vgacap`.
- **Stream step 2:** run as written in [`how-to-capture-stream.md`](https://github.com/mithro/vgacap/blob/59d37c0/python/ttcap/how-to-capture-stream.md): `uv run ttcap capture serial:/dev/ttyACM0 --clock-hz 400000 --seconds 4 --out capture.vgacap`.
  - `/dev/ttboard` is a link to `ttyACM0` on this Pi ([`setup.log`](setup.log)).
  - `UV_NO_DEV=1` was exported, so `uv run` did not add the dev group.
- **10 s capture:** this is the same length as the hardware-in-the-loop runs.

The stream step 2 output, verbatim from [`runs.log`](runs.log):

```text
profile=rp2350-dbv3 project=None enable=None
bytes=1524894 samples=1523712 chunks=94 seconds=4.039 overruns=0 dropped=0 rxstall=0 samples_per_s=377250 mem_free=421504
  board: overruns=0 rxstall=0 sysclk_hz=132000000
wrote capture.vgacap
```

`capture.vgacap` decodes to `tt_um_vga_pattern`'s frames. `vgacap-frames` on the workstation gave 3 frames of
640x480@60 with `glitches_total=0` ([`render.log`](render.log)).

## Restore

| When | `clients` | `idle_display` | Enabled | Bridge | Log |
|---|---|---|---|---|---|
| before | 0 | `loaded` | `idle_display` | active | [`status-before.json`](status-before.json) |
| after | 0 | `loaded` | `idle_display` | active | [`status-after.json`](status-after.json) |

- The "before" Enabled value is the `/designs` read in [`setup.log`](setup.log).
- The "after" Enabled value is the `/designs` read at the end of [`runs.log`](runs.log).
- After the captures, `tools/board_restart.py` restarted the stock firmware (step 5).
- The bridge was started again (step 6). The idle display read `loaded` 72 s later (step 7, [`runs.log`](runs.log)).
- `fuser` then showed the bridge's process on `/dev/ttyACM0`.

## Clean-up

- [`cleanup1.log`](cleanup1.log): `~/vgacap`, the uv tarball and its directory, and `~/.local/bin` were removed.
- [`cleanup2.log`](cleanup2.log): the two uv cache entries the run added were removed, leaving `~/.cache/uv` at 80M.
- [`cleanup1.log`](cleanup1.log) lists the cache entries changed after 06:18.
- `simple-v20/pypi/setuptools.rkyv` was only refreshed, and was left.
- 80M and the eight archive entries are what `~/.cache/uv` held before.

The logs are the raw output, copied as they are. [`runs.log`](runs.log) keeps the firmware's terminal colour codes.
