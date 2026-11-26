# Bench run of the vgacap ttcap pages (PR #43) on fpga-1 and fpga-4

Date: 2026-11-26 (UTC). Code: vgacap 73b7f57, branch `docs-ttcap`
([mithro/vgacap#43](https://github.com/mithro/vgacap/pull/43)), run as a
`git archive` of that commit. Every ttcap how-to on that branch was
followed as written, except the tutorial and the pages for tt09: claiming a
chip board through the broker needs Tim's approval, which was not asked for.

- **fpga-1:** RP2350 demo board with an FPGA breakout, USB serial
  4df39a7a6856f86f, on pi-sw2-p34; MicroPython 970468103d (2026-09-08).
  The USB serial runs ran on fpga-1's own Pi, from a copy of the commit in
  `/home/pi/bench43` (`fpga1-pi-setup.log`), as `serial:/dev/ttyACM0`.
  The bridge runs ran from a workstation through an SSH tunnel to the
  bridge (`ws://127.0.0.1:18034/serial`).
- **fpga-4:** RP2350 demo board with an FPGA breakout, USB serial
  a2961e5cac65b25f, on pi-sw2-p35 (Raspberry Pi 4, 64-bit kernel, 32-bit
  Raspbian 12 userland); MicroPython 970468103d, which boots as `TT SDK
  v3.1.1` (`fpga4-pi-steps.log`). fpga-1 runs the same MicroPython build,
  so its SDK is taken to be 3.1.1 too; its boot banner was not recorded.

## Bridge stops on fpga-1's Pi

Each group of USB serial runs on fpga-1's Pi was bracketed by a bridge stop
(at 0 clients) and start. Each `fpga1-bridge-start<n>.log` shows
`fpgas-tt` active again, with its `status.json` at `"clients": 0`:

| group | runs | stop | start |
|---|---|---|---|
| 1 | the stream captures and USB throughput | `fpga1-bridge-stop1.log` | `fpga1-bridge-start1.log` |
| 2 | `--ui-in` | `fpga1-bridge-stop2.log` | `fpga1-bridge-start2.log` |
| 3 | `--mode window` | `fpga1-bridge-stop3.log` | `fpga1-bridge-start3.log` |
| 4 | `--mode frame`, the reboots and the SDK restart | `fpga1-bridge-stop4.log` | `fpga1-bridge-start4.log` |

## Stream capture on USB serial: 750 kHz is no longer lossless

The design was the one already enabled; each capture was 4 s.

| board | clock | `--buf-words` | overruns | dropped | samples/s | log |
|---|---|---|---|---|---|---|
| fpga-1 | 750 kHz | 4096 | 7 | 114688 | 705606 | `stream-750k-a.log` |
| fpga-1 | 750 kHz | 4096 | 6 | 98304 | 706296 | `stream-750k-b-bufwords-700k.log` |
| fpga-1 | 750 kHz | 16384 | 1 | 65536 | 695718 | `stream-750k-b-bufwords-700k.log` |
| fpga-1 | 700 kHz | 4096 | 3 | 49152 | 659436 | `stream-750k-b-bufwords-700k.log` |
| fpga-1 | 650 kHz | 4096 | 2 | 32768 | 611153 | `stream-650k-600k-500k.log` |
| fpga-1 | 600 kHz | 4096 | 2 | 32768 | 564988 | `stream-650k-600k-500k.log` |
| fpga-1 | 500 kHz | 4096 | 0 | 0 | 471046 | `stream-650k-600k-500k.log` |
| fpga-4 | 750 kHz | 4096 | 7 | 114688 | 704635 | `fpga4-pi-steps.log` |

The 500 kHz row is the only run at 500 kHz on USB serial, and it lasted
4 s. On 2026-11-24, before SDK 3.1.1, a 750 kHz capture on fpga-4 had no
overrun ([direct-serial result](../2026-11-24-direct-serial-fpga4/README.md)).
Throughput is unchanged: `ttcap throughput` gave 716.1 and 713.7 KB/s on
fpga-1's USB serial (`stream-750k-a.log`, `stream-750k-b-bufwords-700k.log`)
and 709.5 KB/s through its bridge (`bridge-throughput.log`).

## Stream capture through the bridge

From the workstation, through the tunnel, `tt_um_vgacal_bars`:

| clock | length | overruns | log |
|---|---|---|---|
| 500 kHz | 10 s | 1 | `bridge-step5.log` |
| 500 kHz | 10 s | 1 | `bridge-step5-try2.log` |
| 500 kHz | 10 s | 2 | `bridge-step5-try3.log` |
| about 500 kHz | 19.5 s | 5 | `stdout-term.log` |
| 400 kHz | 10 s | 0 | `bridge-step5-400000.log` |
| 300 kHz | 10 s | 0 | `bridge-step5-300000.log` |

The 19.5 s row is the standard-output run below (`stdout-run.sh`:
`ttcap capture ws://127.0.0.1:18034/serial --clock-hz 500000 --seconds 0
--out -` piped into `gst-launch-1.0 fdsrc`), with 493758 samples/s.

## Frame, window and inputs (fpga-1's Pi, 25 MHz and up)

- `--mode window --window-lines 48` of `tt_um_vgacal_grid`: 0 overruns, and
  the note was exactly the page's: "each picture is assembled from 11
  captured frames (48 of its 481 lines per frame)" (`window.log`).
- `--mode frame --frames 2` of `tt_um_vgacal_bars` at 25.175 MHz and at
  25 MHz: 2 pictures each, `partial=0 glitches=0` (`frames.log`, `png2.log`).
- `--ui-in 1` and `--ui-in 2` on `tt_um_vgacal_modes`: 800x600@60 at 40 MHz
  and 720x400@70 at 28.322 MHz, one picture each, `partial=0` (`uiin.log`,
  `png2.log`).

## Demo, standard output and reboot (fpga-1)

- `ttcap demo` through the bridge tunnel, 500 kHz, `--fps 5`, 12 s: 51 PNGs
  in `video/` and a 19.8 KiB `video/capture.mkv`; the mode line is printed
  once when detected and again in the summary (`demo.log`).
- `ttcap capture --out -` into `gst-launch-1.0 fdsrc`, through the tunnel:
  stderr ends with `wrote stdout` and then `capture ended: the consumer
  closed the stream` (`stdout-term.log`).
- On fpga-1's Pi, `ttcap reboot --to bootsel` printed `the board runs
  micropython` and `rebooting to bootsel`; the board came back as `RP2350
  Boot` (`reboot1.log`).
- Back to the stock firmware: the vgacap firmware's UF2 was copied onto the
  boot drive, and the board came up as `vgacap capture firmware`
  (`reboot2-load-vgacap-fw.log`). `ttcap reboot --firmware picosdk --to
  flash` then printed `rebooting to flash`, and the board came back as
  `MicroPython Board in FS mode` on `/dev/ttyACM0` (`reboot3-back-to-flash.log`).
  After the SDK restart and the bridge start, `status.json` showed
  `"clients": 0` and `idle_display.state` `waiting` (`fpga1-bridge-start4.log`),
  then `loaded` (`restore-after-board-restart.log`).

## Restoring a bench board

- After `tools/board_restart.py` through the bridge, `status.json`'s
  `idle_display.state` read `loaded` after 61 s (`restore-bridge-step7.log`).
- On fpga-4's Pi, after the SDK restart and `systemctl start fpgas-tt`, it
  read `loaded` after 66 s (`fpga4-restore-step8.log`).
- `safe_start.state` is the field that carries a chip board's `left: ...`
  report (`status-chip-board-left.json`, a chip board on pi-sw2-p2), and it
  reads `not a chip board` on an FPGA board (`status-fpga1-before.json`).

## The Raspberry Pi recipe (fpga-4's Pi)

`getconf LONG_BIT` printed 32. The static uv 0.10.8 armv7 build installed
to `~/.local/bin`, and `UV_NO_DEV=1 uv sync` installed exactly 3 packages:
pyserial 3.5, vgacap 0.0.1 and websockets 17.1 (`fpga4-pi-recipe.log`). The
Pi also has uv 0.13.1 (armv7-unknown-linux-gnueabihf) in `/usr/local/bin`,
which a shell without `~/.local/bin` first on `PATH` will find
(`fpga4-preinstalled-uv.log`). On a bench Pi, `ttcap probe` of the board
needs `fpgas-tt` stopped first.

## tt07 and tt09, through their bridges

Later the same day (from 23:05 UTC), at vgacap 3cc3f95, the tutorial ran
on tt07 and the frame and run-length pages on tt09. Pi SSH was down, so
both ran from a workstation through an SSH tunnel to each board's bridge.

- **tt07:** `tt-de641070db746f27`, an RP2040 demo board with a Tiny
  Tapeout 7 chip, on pi-sw2-p7. The probe printed `MicroPython v1.24.0 on
  2024-10-25`, with `'rp_projclk': 0` and `'uo_out0': 5` (`tt07-probe.log`).
- **tt09:** `tt-3b0880b48ee5c388`, an RP2350 demo board with a Tiny Tapeout
  9 chip, on pi-sw2-p10. The probe printed `MicroPython 970468103d on
  2026-09-08` (`tt09-probe.log`).

The tutorial on tt07 (`tt_um_rejunity_vga`, 60 kHz, `--frames 2`):

- The first capture failed with `board error: MemoryError: memory
  allocation failed, allocating 16384 bytes`, `bytes=0` and
  `mem_free=74880`, exited 1, and still printed `wrote capture.vgacap`
  (`tt07-capture-memoryerror.log`).
- After an SDK restart with `tools/board_restart.py` (`tt07-sdk-restart.log`),
  the same command captured 1687552 samples in 28.65 s with no overrun,
  `mem_free=81008` (`tt07-capture-retry.log`).
- `ttcap png` wrote 3 PNGs, each `partial=0 glitches=0`, `frames=3
  glitches_total=0` (`tt07-png.log`).

On tt09:

- `--mode frame` of `tt_um_rejunity_vga_logo` at 25.175 MHz: 2 pictures,
  0 overruns. The board's heap held 410 of the picture's 481 lines, so
  each picture is two captured frames (`tt09-frames.log`). The design
  dithers every frame, so `tt09-logo-frame-torn.png` changes below about
  line 410, where the second frame takes over.
- `--mode rle` of `tt_um_vga_clock`, the page's command (100 kHz, 14 s): 1514018 samples in
  82117 bytes, `rle style=edge period=1500 mask=1`, 0 overruns, and 2
  pictures at 640x480@72 (`tt09-rle.log`).

`safe_start.state` before and after: on tt07 it read `set: clock stopped
...` both times (`tt07-status-before.json`, `tt07-status-after.json`). On
tt09 it read `failed: the board did not take the safe state` both times
(`tt09-status-before.json`, `tt09-status-after.json`), as it already did
before this run.

## Other boards seen

The site registry (`registry.txt`) lists chip boards on pi-sw2-p3, p6, p7
and p8. Their board pages (`board-pages-attrs.log`) name the shuttles
tt03p5, tt06, tt07 and tt08. tt07 (`tt-de641070db746f27`, pi-sw2-p7) and
tt06 (`tt-de640cb1d3357125`, pi-sw2-p6) are "operational" in the registry,
and their pages give a WebSocket path. Of these, only tt07 was probed and captured, as above.
