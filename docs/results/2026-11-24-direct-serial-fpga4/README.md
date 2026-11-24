# Direct serial ownership on the Pi (M7): stream and frame capture on fpga-4

Date: 2026-11-24. Board: fpga-4 (pi-sw2-p35, USB serial a2961e5cac65b25f,
Tiny Tapeout demo board v3, RP2350, SDK 3.1.0). Design: `tt_um_vgacal_bars`,
uploaded and enabled through the daemon before each run.

This is the design's "high-performance path": the capture owns
`/dev/ttboard` on the board's own Pi instead of going through the
`fpgas-tt` websocket bridge. Run as `ssh ... 'bash -s' < direct_serial.sh`.
The script:

1. Refuses to run if the bridge has any client (`/health` `clients` is not
   0), so it never cuts off a visitor's session.
2. Stops `fpgas-tt`.
3. Runs `ttcap` from a copy of `vgacap/python`, under a static uv
   (`uv-armv7-unknown-linux-musleabihf` 0.10.8). The Pi has a 64-bit kernel
   but a 32-bit userland, so the aarch64 glibc build has no loader. Python
   is the Pi's 3.11, with pyserial and websockets.
4. Starts `fpgas-tt` again from an EXIT trap, so the service comes back
   even when a step fails, and logs `systemctl is-active`.

| run | bridge down | result |
|---|---|---|
| `ttcap throughput serial:/dev/ttboard` | 11:26:43–11:26:52Z (9 s, both rows) | 700.0 KB/s, not corrupt |
| `ttcap capture` streaming at 750 kHz, 4 s | (same window) | 2,834,432 samples, 0 overruns, rxstall 0; 6 frames, 0 glitches; frame 2 pixel-identical to the reference (307,200 pixels) |
| `ttcap capture --mode frame` at 25 MHz, 3 frames | 11:27:18–11:27:22Z (4 s) | 3 pictures, each pixel-identical to the reference (`frame_25mhz_direct.ppm` is one) |

For comparison, the same throughput test through the bridge (tunnelled to
big-storage) gave 712.8 KB/s. The bridge costs nothing measurable here:
the RP2350's USB CDC link is the limit either way. Direct ownership
matters for avoiding the shared hop and the bridge's fan-out to other
clients. ## Also on the tt09 ASIC board (sw2 p10, the slower Pi)

The same script on tt09 (USB serial 3b0880b48ee5c388, SDK 3.0.7), on its
32-bit armv7 Pi:

| path | throughput |
|---|---|
| bridge (tunnelled websocket) | 179.3, 179.2 KB/s |
| direct `/dev/ttboard`, fpgas-tt stopped 11:30:03–11:30:28Z | 178.3, 179.1 KB/s |

On that Pi as well the two are the same, so the 4x gap to fpga-4's Pi
lies below the bridge, in that Pi's USB path. Real silicon over the direct
path: `ttcap capture --project tt_um_rejunity_vga_logo --mode frame
--clock-hz 25175000 --frames 2` gave 2 pictures, 0 overruns, 0 glitches,
positive/positive sync (`tt09_logo_direct.png`). The design dithers
randomly every frame and its shading moves, so consecutive pictures
differ (~119,000 pixels) as they did through the bridge earlier today; it
has no reference render to compare against.

Restoring tt09 took an extra step. The daemon runs its "safe start" check
when it starts, so restarting it while the logo was still enabled left it
reporting `left: tt_um_rejunity_vga_logo is enabled`. That stayed after
an SDK restart, until fpgas-tt was restarted again (clients 0) on the
default project. It then returned to its pre-existing `failed: the board
did not take the safe state`, exactly as the morning's survey found it.
**A direct capture on an ASIC board should restart the SDK *before*
starting fpgas-tt again.**

Afterwards `fpgas-tt` was `active` and the board was restored: SDK
restarted (Ctrl-B, Ctrl-D), idle display `loaded`, claim removed.
