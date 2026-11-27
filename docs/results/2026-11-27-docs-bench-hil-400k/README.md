# Hardware-in-the-loop check at 400 kHz through the bridge on fpga-1

Date: 2026-11-27 (UTC). Code: vgacap 20f99bf, branch `docs-developing`
([mithro/vgacap#33](https://github.com/mithro/vgacap/pull/33)), and
tt-vga-testpatterns 1ff01b1. Steps 3 and 4 of vgacap's
`tools/how-to-run-hil-through-a-tunnel.md` were run four times in a row,
from a workstation through an SSH tunnel to the bridge
(`ws://127.0.0.1:18034/serial`).

- **Board:** fpga-1, RP2350 demo board with an FPGA breakout, USB serial
  4df39a7a6856f86f, on pi-sw2-p34; MicroPython 970468103d (2026-09-08).
- **Claim:** `c-ejFCbzM3baPC` through the fpgas.online broker, released
  at 01:48:00Z.
- **Design:** `tt_um_vgacal_bars`, uploaded and enabled at 400 kHz before
  each run (`run<n>-step3.log`).

The [2026-11-26 bench run](../2026-11-26-docs-bench-ttcap/README.md) found
that a stream capture through the bridge overruns at 500 kHz and is clean at
400 kHz. These runs check the whole hardware-in-the-loop check at 400 kHz.

## Runs

Every run passed all ten checks, with no skip, and exited 0. The capture
column is from the `capture` check, and reference from the `reference`
check (`run<n>-step4.log`, `run<n>-hil-report.md`, `run<n>-times.log`).

| run | step 4 start | step 4 wall time | checks | capture samples | seconds | overruns | dropped | samples/s | frames | reference |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 01:43:50Z | 35.8 s | 10 passed | 3915776 | 10.035 | 0 | 0 | 390204 | 8 | 307200 pixels identical |
| 2 | 01:44:42Z | 34.0 s | 10 passed | 3915776 | 10.033 | 0 | 0 | 390276 | 8 | 307200 pixels identical |
| 3 | 01:45:20Z | 33.4 s | 10 passed | 3915776 | 10.032 | 0 | 0 | 390328 | 8 | 307200 pixels identical |
| 4 | 01:45:58Z | 33.0 s | 10 passed | 3915776 | 10.033 | 0 | 0 | 390294 | 8 | 307200 pixels identical |

In every run the `frame` check gave 2 of 2 pictures pixel-exact at
25 MHz, with `stalls=0 rxstall=0`, and the `stop` check exited 0 within
0.26 s of SIGTERM with no orphan.

## Restore

Step 5 (`tools/board_restart.py`) restarted the stock firmware, ending at
its `>>>` prompt at 01:46:42Z (`step5-restart.log`, colour codes removed).
The idle display read `loaded` 66 s later, polled every 5 s
(`idle-poll.log`). `status-before.json` (01:42:44Z) and `status-after.json`
both show `"clients": 0` and `idle_display` `"state": "loaded"`. The tunnel
was closed by killing its `ssh` process.
