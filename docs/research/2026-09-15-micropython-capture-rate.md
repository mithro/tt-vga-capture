# MicroPython capture: project clock sweep on both board types

Date: 2026-09-15. `vgacap` 4783a08, `ttcap capture` run ON the Pi over direct
serial (`fpgas-tt` stopped for the runs, restarted after), `--profile auto`,
sampler on PIO1, default 4096-word buffers on fpga-1 and 1024-word buffers
on tt07 (its heap is small). "dropped" is the board's cumulative count of
samples overwritten before the host loop could send them.

## fpga-1 (RP2350, `tt_um_vga_pattern`, 8 s each, 1 byte per sample)

| clock | samples | samples/s | overruns | dropped |
|---|---|---|---|---|
| 500 kHz | 3,883,008 | 484,205 | 0 | 0 |
| 750 kHz | 5,832,704 | 726,962 | 0 | 0 |
| 1 MHz | 6,062,080 | 754,830 | 106 | 1,736,704 |
| 1.5 MHz | 6,455,296 | 802,289 | 320 | 5,242,880 |

The MicroPython loop saturates around 750-800 k samples/s (matches the
~650-740 KB/s USB CDC measurement). Clean ceiling: **750 kHz** project
clock, i.e. a 640x480 frame every 0.56 s.

## tt07 (RP2040, `tt_um_rejunity_vga`, 12 s each, 2 bytes per sample)

| clock | samples | samples/s | overruns | dropped |
|---|---|---|---|---|
| 60 kHz | 696,320 | 57,732 | 0 | 0 |
| 75 kHz | 866,304 | 71,825 | 2 | 4,096 |
| 100 kHz | 0 | — | — | board `OSError: [Errno 12] ENOMEM` at setup (see below) |

Clean ceiling on the RP2040 firmware: **60 kHz** (a frame every 7 s);
75 kHz drops a buffer every few seconds.

## The ENOMEM at 100 kHz is not about the clock

The error came from the state-machine setup line of the script and
appeared on the eleventh-or-so capture since the board's last power cycle.
Each run adds the 3-instruction sampler to PIO1's 32-slot instruction
memory and never removes it; ten runs fill it. Fix: remove the program in
the script's `finally` (and defensively before adding). Tracked as a
follow-up in `vgacap`.

## Consequences

- Slow-clock streaming with the stock firmware: 750 kHz (RP2350) and
  60 kHz (RP2040). Good enough for pictures of every VGA project, at 2 to
  7 s per frame.
- Anything faster needs whole-frame capture into SRAM (RP2350 has ~397 KB
  free at capture time: a 640x480 frame with blanking is 420,000 samples,
  so the active area or a compressed frame fits), compression, or the C
  firmware (Milestone 7).
- The overrun accounting works and is exact (dropped = overruns x buffer
  samples); the CLI should coalesce the per-chunk "board: overrun" lines.
