# Bench run of the vgacap firmware, module, GStreamer and HIL pages on fpga-1 and tt09

Date: 2026-11-27 (UTC), 01:05 to 01:32. Approved by Tim on 2026-11-27, the
module flash included. Three vgacap docs PRs were followed as written:

- [mithro/vgacap#42](https://github.com/mithro/vgacap/pull/42) at 08ccd16:
  the vgacap firmware and the MicroPython module;
- [mithro/vgacap#36](https://github.com/mithro/vgacap/pull/36) at 16a4fa4:
  the GStreamer plugin, live;
- [mithro/vgacap#33](https://github.com/mithro/vgacap/pull/33) at cacc0ed:
  the hardware-in-the-loop check.

Boards:
- **fpga-1:** RP2350 demo board with an FPGA breakout, USB serial
  4df39a7a6856f86f, on pi-sw2-p34. It ran stock MicroPython 970468103d
  (2026-09-08) with SDK 3.1.1 and 46 files.
- **tt09:** RP2350 demo board with the TT09 ASIC, USB serial
  3b0880b48ee5c388.

Claims, both under Tim's 2026-11-27 approval, made through the fpgas-online
broker:

| board | claim | claimed | released |
|---|---|---|---|
| fpga-1 (`welland:pi-sw2-p34`) | `c-rNYD_FE9L_dp` | 01:01:00 UTC | 01:33:05 UTC |
| tt09 | `c-L3lBpCRo6XOc` | -- | 01:17:14 UTC |

Logs are copied with NUL bytes, ANSI colour codes and the SDK's boot banner
taken out. Every log below is in this directory.

## 1. The vgacap firmware: load and capture on fpga-1

`fw_load.log`, `fw_capture.log`, `enable_design.log`.

- Loading followed the load page: the bridge stopped at 0 clients,
  `ttcap reboot --to bootsel`, the UF2 copied, the port
  `usb-vgacap_vgacap_capture_firmware_4DF39A7A6856F86F-if00` (2e8a:0009),
  `ttcap reboot` back to stock, the bridge started again.
- The first frame and window captures failed with `board went quiet`: no
  design was enabled. `tt_um_vga_pattern` is an uploaded design, which
  `tt.shuttle` does not know; it was enabled through the bridge with
  `POST /designs/tt_um_vga_pattern/enable`, then the firmware loaded again.
- `ttcap png` failed on the Pi, which has no `vgacap-frames` (no CMake). It
  ran on a workstation checkout at 08ccd16 instead.

| capture | clock | result | board report |
|---|---|---|---|
| frame, 2 pictures | 25 MHz | 769600 samples, 737287 samples/s | `frame window=481 buffers=1`, `frames=2 stalls=0 rxstall=0 sysclk_hz=100000000` |
| window, 48 lines | 25 MHz | 384800 samples, 595018 samples/s | `frame window=48 buffers=1`, `frames=1` |
| stream, 4 s | 750 kHz | 2998272 samples, **746351 samples/s**, 0 overruns | `overruns=0 rxstall=0 sysclk_hz=132000000` |
| `ttcap png` of the frame capture | -- | 2 frames, 0 glitches | -- |

## 2. The module firmware: flash, capture and restore on fpga-1

`module_flash.log`, `module_capture.log`, `sdk_restart.log`.

The image was the `dev-vgacap-module` release asset
`tt-demo-rp2350-vgacap-module-v3.1.1-dev-14a09314.uf2`. The tools came from
tt-vga-capture at e4427aa.

| point | firmware region SHA-256 | files |
|---|---|---|
| backup (step 5) | `b57a7ffc4856e0ca997f551a0e88c4651df72f1ca246a7e48f681cd85d5eb6d1` MATCH | 46 match, 0 do not |
| restore image (step 7) | `b57a7ffc…`, equal to the backup | -- |
| filesystem start (step 8) | littlefs magic at `0x100c8008` | -- |
| `module.bin` (step 6) | `5dc230b2bc8703a2493165b9e2eca2c8fbfeb443b027a0da41669a992b6ece64` | -- |
| module firmware (step 11) | `5dc230b2…`, equal to `module.bin` | identical (step 12) |
| `import vgacap` (step 13) | `API` 1 | -- |
| after restore path A, through the REPL | `b57a7ffc…` | identical |
| after restore path B, drive only | `b57a7ffc…` | identical |

- Path A: no `RP2350` drive at step 15, so `mpremote connect $DEV bootloader`
  brought it up. Path B: BOOTSEL forced first with the same command, so step
  15 found the drive and skipped the reboot.
- After the restores `import vgacap` failed with `ImportError`, as on stock.
- The module capture first failed with `NameError: name 'tt' isn't defined`:
  after the flash the SDK's `main.py` had not run. `tools/board_restart.py`
  restarted it. `--project tt_um_vga_pattern` then failed with `not a shuttle
  entry on this board ... has to be enabled through the board's daemon
  first`; the design was enabled through the bridge.

| capture | clock | result | board report |
|---|---|---|---|
| frame, 2 pictures | 25 MHz | 769600 samples, 762212 samples/s, `mem_free=421632` | `frame window=481 buffers=52`, `frames=2 stalls=0 rxstall=0 sysclk_hz=100000000` |
| window, 48 lines | 25 MHz | 384800 samples, 563085 samples/s | `frame window=48 buffers=1`, `frames=1` |
| stream, 4 s | 500 kHz | 2015232 samples, **501606 samples/s**, 0 overruns | `overruns=0 rxstall=0 sysclk_hz=133000000` |
| `ttcap png` of the frame capture, on the workstation | -- | 2 frames, 0 glitches | -- |

After step 18 the idle display stayed at `left: the SDK is not running` until
`tools/board_restart.py` ran (`sdk_restart.log`).

## 3. tt09: `asic_select`

`tt09_load.log`, `tt09_select.log`, `tt09_png.log`, `tt09_restore.log`,
`tt09_final.log`.

The index came from the shuttle index:

```
$ curl -s 'https://index.tinytapeout.com/tt09.json?fields=address' | jq '.projects[] | select(.macro == "tt_um_rejunity_vga_logo") | .address'
806
```

The capture, through the vgacap firmware loaded from RAM:

```
$ uv run --no-sync ttcap capture --firmware picosdk serial:/dev/serial/by-id/usb-vgacap_vgacap_capture_firmware_3B0880B48EE5C388-if00 --asic-index 806 --clock-hz 25175000 --mode frame --frames 2 --out frame.vgacap
profile=rp2350-dbv3 project=None enable=kept (capture firmware)
bytes=769803 samples=769600 chunks=4 seconds=4.011 overruns=0 dropped=0 rxstall=0 samples_per_s=191886
  board: frame window=481 buffers=1 hsync_active=1 vsync_active=1
  board: frames=2 stalls=0 rxstall=0 sysclk_hz=101000000
wrote frame.vgacap
```

A second capture with the same `--asic-index` gave the same report. `ttcap
png` on the workstation rendered 2 frames, positive syncs, 0 glitches. The
board went back to stock with `ttcap reboot`. Its safe-start state then read
`left: the factory test is not being clocked`, and after `mpremote ... reset`
it returned to `set: clock stopped ...`, as before the run.

## 4. #36: the GStreamer plugin, live

`pr36_live.log`, `pr36_live_mkv.log`.

`vgacapbin` with `tt-ws://127.0.0.1:18034/serial?design=tt_um_vga_pattern&clock-hz=500000&seconds=10`,
through an SSH tunnel to fpga-1's bridge, into x264 and Matroska. The first
attempt failed the same way as section 2: the design had to be enabled
through the bridge. The second ran 10.6 s and wrote a video of **10 frames
at 1.19 fps** (`avg_frame_rate=25/21`).

## 5. #33: the hardware-in-the-loop check

`pr33_hil_pi.log`, `pr33_hil_tunnel.log`, `pr33_hil_tunnel_run2.log`,
`pr33_restart_wait.log`, `restart_wait_final.log`.

- **On the Pi** (`tools/hil.py --link serial:/dev/ttboard --no-demo
  --stop-bridge`, `tt_um_vgacal_bars` at 500 kHz): 4 passed, 0 failed,
  6 skipped. The capture was 4898816 samples with 0 overruns, and 11 frames
  rebuilt with 0 glitches. The Pi has no CMake; `vgacap-frames` was built
  with `uvx --from cmake cmake`.
- **Through the tunnel** (`ws://127.0.0.1:18034/serial`): the `capture`
  check failed at 500 kHz with 3 overruns (49152 samples dropped), and on a
  second run with 1 (16384). The demo, video, serve and stop checks passed
  both times.
- **SDK restart to `loaded`:** after `tools/board_restart.py` the idle
  display read `waiting`, then `loaded` after 66 to 73 s.

## 6. The board left as found

`final_fw_check.log`, `final_state.log`.

fpga-1's firmware region read `b57a7ffc…` again over the public bridge,
MicroPython 970468103d with SDK 3.1.1, and its idle display read `loaded`
with 0 clients. tt09 was back on its stock firmware with its pre-existing
safe-start state. No power cycle was needed.
