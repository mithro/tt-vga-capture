# Bench run of the vgacap ttcap pages (PR #43) on fpga-1 and fpga-4

Date: 2026-11-26 (UTC). Code: vgacap 73b7f57, branch `docs-ttcap`
([mithro/vgacap#43](https://github.com/mithro/vgacap/pull/43)), run as a
`git archive` of that commit. Every ttcap how-to on that branch was
followed as written, except the tutorial and the pages for tt09: claiming a
chip board through the broker needs Tim's approval, which was not asked for.

- **fpga-1:** RP2350 demo board with an FPGA breakout, USB serial
  4df39a7a6856f86f, on pi-sw2-p34; MicroPython 970468103d (2026-09-08).
  Run from a workstation on its USB serial (`/dev/ttyACM0`) and through
  its bridge over an SSH tunnel.
- **fpga-4:** RP2350 demo board with an FPGA breakout, USB serial
  a2961e5cac65b25f, on pi-sw2-p35 (Raspberry Pi 4, 64-bit kernel, 32-bit
  Raspbian 12 userland); MicroPython 970468103d, which boots as `TT SDK
  v3.1.1` (`fpga4-pi-steps.log`).

## Stream capture: 750 kHz is no longer lossless

The design was the one already enabled; each capture was 4 s.

| board | path | clock | `--buf-words` | overruns | dropped | samples/s | log |
|---|---|---|---|---|---|---|---|
| fpga-1 | USB serial | 750 kHz | 4096 | 7 | 114688 | 705606 | `stream-750k-a.log` |
| fpga-1 | USB serial | 750 kHz | 4096 | 6 | 98304 | 706296 | `stream-750k-b-bufwords-700k.log` |
| fpga-1 | USB serial | 750 kHz | 16384 | 1 | 65536 | 695718 | `stream-750k-b-bufwords-700k.log` |
| fpga-1 | USB serial | 700 kHz | 4096 | 3 | 49152 | 659436 | `stream-750k-b-bufwords-700k.log` |
| fpga-1 | USB serial | 650 kHz | 4096 | 2 | 32768 | 611153 | `stream-650k-600k-500k.log` |
| fpga-1 | USB serial | 600 kHz | 4096 | 2 | 32768 | 564988 | `stream-650k-600k-500k.log` |
| fpga-1 | USB serial | 500 kHz | 4096 | 0 | 0 | 471046 | `stream-650k-600k-500k.log` |
| fpga-4 | its Pi, `/dev/ttboard` | 750 kHz | 4096 | 7 | 114688 | 704635 | `fpga4-pi-steps.log` |

On 2026-11-24, before SDK 3.1.1, the same 750 kHz capture on fpga-4 had no
overrun ([direct-serial result](../2026-11-24-direct-serial-fpga4/README.md)).
Throughput is unchanged: `ttcap throughput` gave 716.1 and 713.7 KB/s on
fpga-1's USB serial (`stream-750k-a.log`, `stream-750k-b-bufwords-700k.log`)
and 709.5 KB/s through its bridge (`bridge-throughput.log`). So the link
still carries 700 KB/s, and the overruns come from the board's loop.

Through the bridge (10 s each, `tt_um_vgacal_bars`):

| clock | overruns | log |
|---|---|---|
| 500 kHz | 1 | `bridge-step5.log` |
| 500 kHz | 1 | `bridge-step5-try2.log` |
| 500 kHz | 2 | `bridge-step5-try3.log` |
| 400 kHz | 0 | `bridge-step5-400000.log` |
| 300 kHz | 0 | `bridge-step5-300000.log` |

## Frame, window and inputs (fpga-1, 25 MHz and up)

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
- `ttcap capture --out -` into `gst-launch-1.0 fdsrc`: stderr ends with
  `wrote stdout` and then `capture ended: the consumer closed the stream`
  (`stdout-term.log`).
- `ttcap reboot --to bootsel` printed `the board runs micropython` and
  `rebooting to bootsel`; the board came back as `RP2350 Boot`
  (`reboot1.log`).

## Restoring a bench board

- After `tools/board_restart.py` through the bridge, `status.json`'s
  `idle_display.state` read `loaded` after 61 s (`restore-bridge-step7.log`).
- On fpga-4's Pi, after the SDK restart and `systemctl start fpgas-tt`, it
  read `loaded` after 66 s (`fpga4-restore-step8.log`).
- `safe_start.state` is the field that carries a chip board's `left: ...`
  report (`status-chip-board-left.json`, a chip board on pi-sw2-p2), and it
  reads `not a chip board` on an FPGA board (`status-fpga1-before.json`).

## The Raspberry Pi recipe (fpga-4's Pi)

`getconf LONG_BIT` printed 32 (`fpga4-pi-longbit.log`). The static uv
0.10.8 armv7 build installed to `~/.local/bin`, and `UV_NO_DEV=1 uv sync`
installed exactly 3 packages: pyserial 3.5, vgacap 0.0.1 and websockets
17.1 (`fpga4-pi-recipe.log`). The Pi already had uv 0.13.1
(armv7-unknown-linux-gnueabihf) in `/usr/local/bin`, which comes first on
`PATH` unless `~/.local/bin` is put before it (`fpga4-preinstalled-uv.log`).
On a bench Pi, `ttcap probe` of the board needs `fpgas-tt` stopped first.

## Other boards seen

The site registry (`registry.txt`) lists chip boards on pi-sw2-p3, p6, p7 and
p8, whose pages name the shuttles tt03p5, tt06, tt07 and tt08. tt07
(`tt-de641070db746f27`, pi-sw2-p7) is "operational" with a published
WebSocket path. None of them was probed in this run.
