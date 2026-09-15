# The calibration loop closes: pixel-exact capture of a known design

Date: 2026-09-15. This is the end-to-end validation the project was built
for: a Verilog design of known content, synthesised to an iCE40UP5K
bitstream, loaded onto a real Tiny Tapeout FPGA emulation board at Welland,
captured through the demo board's PIO, streamed over USB, reconstructed by
`libvgaframe`, and compared pixel by pixel against the reference renderer
that describes what the design was supposed to draw.

Both designs matched **all 307,200 pixels** with no exceptions, no
tolerance and no alignment fudge.

## What ran

Board: fpga-1 (pi-sw2-p33), Tiny Tapeout demo board v3 (RP2350B, stock
MicroPython firmware) with the FabricFox iCE40UP5K breakout. Sampler on
PIO1 at a 500 kHz project clock, falling edge, 8 bits per sample.

```
# tunnel: ssh -N -L 18733:10.21.2.33:8765 tweed.welland.mithis.com
cd tt-vga-testpatterns
uv run --no-project python tools/upload.py http://127.0.0.1:18733 \
    bitstreams/tt_um_vgacal_bars.bin --enable --clock-hz 500000
cd ../vgacap
uv run ttcap capture ws://127.0.0.1:18733/serial --profile rp2350 \
    --design tt_um_vgacal_bars --clock-hz 500000 --seconds 10 --pio 1 \
    --out tmp/cal_bars_fpga1.vgacap
./build/vgacap-frames tmp/cal_bars_fpga1.vgacap tmp/calbars/f
cd ../tt-vga-testpatterns
uv run --no-project --with numpy --with pillow python tools/compare_capture.py \
    tt_um_vgacal_bars ../vgacap/tmp/calbars/f-0005.ppm
```

## Results

| design | samples | overruns | frames | comparison |
|---|---|---|---|---|
| `tt_um_vgacal_bars` | 4,882,432 | 0 | 10 | PASS, 307,200 pixels identical |
| `tt_um_vgacal_grid` | 4,882,432 | 0 | 10 | PASS, 307,200 pixels identical |

Every frame reported `640x480 mode=640x480@60 cpl=800 lpf=525 hsync=neg
vsync=neg partial=0`, and the board reported `overruns=0 rxstall=0`.

64 colour bars of 10 pixels each, the full 6-bit palette the Tiny VGA Pmod
can produce:

![bars](bars-frame.png)

The one-pixel grid on a dark background, which is the strictest test of
sample phase and pixel alignment: a single clock of error anywhere in the
chain would smear or shift every line of it.

![grid](grid-frame.png)

`bars-capture.vgacap.gz` is the full bars stream (4.9 MB raw, 28 KB
gzipped).

## Why this matters

Until now the pipeline had been checked against simulations of other
people's designs, where a disagreement could always be blamed on the
design's own timing (and once was: see `docs/research/` on the VGA
playground's sync phase). These designs were written against the VESA
timings the reconstruction library assumes, so a pixel-exact match means
the capture path itself, PIO sampling phase, DMA, chunk framing, stream
format, sync detection, active-area cropping and colour expansion, is
correct on real hardware.
