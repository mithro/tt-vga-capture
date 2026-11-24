# The pico-sdk capture firmware on fpga-4: pixel-exact, run from RAM

Date: 2026-11-24. Milestone 7, first item.
- **Board:** fpga-4 (pi-sw2-p35, USB serial a2961e5cac65b25f, demo board
  v3, RP2350B, stock MicroPython b006887db6 with SDK 3.1.0, FabricFox
  iCE40UP5K).
- **Firmware:** vgacap branch `fw-picosdk` (3203e08, then 8b85ee7), built
  against pico-sdk 2.2.0 as a **no_flash** UF2, so it runs from SRAM and
  never writes flash.

## What was done (`fw_hil.sh`, run on the board's Pi)

1. Bars was enabled through the daemon at 25 MHz. `fpgas-tt` was stopped
   only while `/health` showed 0 clients; an EXIT trap starts it again.
2. A reference frame capture was taken with the stock firmware, as today.
3. `ttcap reboot serial:/dev/ttboard --to bootsel` put the board in the
   RP2350 boot ROM (USB 2e8a:000f, drive `RP2350`). The UF2 was copied to
   it, and the firmware enumerated as 2e8a:0009 two seconds later.
4. `ttcap capture --firmware picosdk ...`: frame (25 MHz, 2 pictures),
   window (25 MHz, 48 lines) and streaming (750 kHz, 4 s).
5. `ttcap reboot ... --firmware picosdk` (a watchdog reset) brought back
   the stock firmware, `/dev/ttboard`, and then `fpgas-tt`.

`fpgas-tt` was down 12:38:51–12:39:10Z, 19 s. No power cycle was needed.

## Results (`fw_hil.log`, `compare.log`, `stream_continuity.log`)

| capture | firmware | board report | result |
|---|---|---|---|
| frame, 25 MHz | stock MicroPython | window=475 (2 frames per picture), 79 buffers | pixel-exact |
| frame, 25 MHz, 2 pictures | **pico-sdk** | window=**481 buffers=1**, frames=2 stalls=0 rxstall=0, sysclk 100 MHz | both pixel-exact |
| window, 48 lines, 25 MHz | **pico-sdk** | frames=1, 11 captured frames | pixel-exact |
| stream, 750 kHz, 4 s | **pico-sdk** | 2,998,272 samples, 746 k samples/s, overruns 0, rxstall 0 | 6 frames pixel-exact; all samples one unbroken stretch |

Two of the firmware's differences from the MicroPython path are visible
in those numbers:
- **The whole frame fits one buffer.** The firmware owns a 440 KB capture
  buffer, so a 640x480 picture is one captured frame. MicroPython's
  fragmented heap needed 2 frames and 79 buffers.
- **Frame mode delivers about 0.74 M samples/s**, against 0.28 M from the
  stock firmware on the same board and link.

## Things this settled

- **The iCE40 keeps its configuration** while the RP2350 is in the boot
  ROM and switches to this firmware. The firmware's README had flagged
  this as an assumption, because `CRESET_B` (GPIO 1) has only the pad's
  pull-down then. Every capture after the switch was exact.
- **The board was left exactly as it was.** A SHA-256 of every file on its
  filesystem was taken before and after (`board_manifest_before.txt`,
  `board_manifest_after.txt`): 53 files, identical. After an SDK restart it
  reported MicroPython b006887db6 and `tt.sdk_version=3.1.0`, and the
  daemon's idle display returned to `loaded`.

## Still open

- ~~ASIC boards: whether the selected project survives the switch.~~ It
  doesn't, and the firmware now selects it itself; see below.
- **RP2040:** no board is connected anywhere.
- ~~Not wired to the firmware yet: `ttcap demo` and the GStreamer source.~~
  Done and run live; see below.

## Live: GStreamer and `ttcap demo` on the capture firmware

The same board was used a second time (12:52Z), this time with vgacap
branch `fw-demo-gst` (vgacap PR #8): `vgacapttsrc` and `vgacapbin` gained
a `firmware` property, and `ttcap demo` gained `--firmware`.

Steps:
- `fw_load.sh` stopped `fpgas-tt` (clients 0) and loaded the RAM firmware.
- `ttcap demo` ran **on big-storage**, its pipeline using `vgacapttsrc`.
  The element's `ttcap-command` was an `ssh` that runs ttcap on the
  board's Pi against the firmware's serial port. A remote ttcap needs no
  GStreamer on the Pi.
- `fw_restore.sh` did the watchdog reboot to stock, and `fpgas-tt` came
  back. It was down 46 s.

```
ttcap demo --link serial:/dev/serial/by-id/usb-vgacap_vgacap_capture_firmware_A2961E5CAC65B25F-if00 \
    --firmware picosdk --mode frame --clock-hz 25000000 --seconds 12 --fps 2 \
    --outdir fwdemo --ttcap-command "ssh ... pi@10.21.2.35 cd vgacap-run && ... python -m ttcap.cli"
```

Results (`live_demo.log`):
- Mode 640x480@60, 0 glitches, a frame about every 0.5 s, 24 PNGs and an MKV.
- **All 24 frames pixel-identical** to the reference render.
- Board files identical before and after (`board_manifest_*_demo.txt`).
- No power cycle was needed.

![a frame from the live demo](live_demo_frame.png)

## ASIC board: tt09 silicon, with `asic_select`

Board: tt09 (pi-sw2-p10, USB serial 3b0880b48ee5c388, MicroPython
670d775365, SDK 3.0.7). Design: `tt_um_rejunity_vga_logo` at 25.175 MHz.

1. **First run, firmware as in PR #7 (`tt09_no_select.log`).** The stock
   firmware's frame capture was clean. After the switch, the capture
   firmware saw no sync at all, and its frame trigger waited until the
   host timed out. The project-mux lines (GPIO 0/1/2) float while the
   RP2350 is in its bootloader, so the mux comes back with nothing
   selected.
2. **The fix (vgacap PR #9, branch `fw-asic-select`).** A firmware command
   `asic_select index=N` replays the stock SDK's
   `ProjectMux.reset_and_clock_mux()`. `ttcap capture --firmware picosdk
   --asic-index N` sends it, where N is the SDK's
   `tt.shuttle.<name>.count`, 806 for the logo on tt09. It is never used
   on an FPGA carrier, where GPIO 1 is the iCE40's `CRESET_B`. The
   simulated board models the mux.
3. **Second run, with `--asic-index 806` (`tt09_asic_select.log`,
   `fw_hil_asic2.sh`).**
   - 2 pictures, positive/positive sync, 0 glitches, frame window 481
     lines in 1 buffer, no overruns.
   - A clean logo; one picture is `tt09_logo_asic_select.png`.
   - This design dithers randomly every frame, so it has no reference
     render to compare against.
   - The stock firmware needed 2 captured frames per picture on this
     board; the capture firmware needs 1.

Afterwards, tt09 was put back exactly as it was found:
- 46 files hashed identical (`tt09_manifest_*.txt`);
- MicroPython 670d775365 and SDK 3.0.7;
- `fpgas-tt` restarted at 0 clients until its safe-start state was back to
  the pre-existing `failed: the board did not take the safe state`;
- no power cycle was needed.

![tt09 logo through the capture firmware](tt09_logo_asic_select.png)

### tt09: window and stream through the firmware too (`tt09_window_stream.log`)

A third run, same procedure with `--asic-index 806`:
- **Window, 25.175 MHz:** 48 lines, a picture from 11 frames; 0 glitches,
  positive/positive sync.
- **Stream, 175 kHz for 6 s:** 1,048,576 samples (172.5 k/s, the most
  this Pi 3B+ carries); overruns 0, rxstall 0; a frame reconstructed with
  0 glitches (`tt09_logo_stream.png`).

So the firmware's stream, frame and window captures have all run on
silicon. The board was put back with its 46 files identical and its
pre-existing safe-start state.

![tt09 logo, streamed through the capture firmware](tt09_logo_stream.png)
