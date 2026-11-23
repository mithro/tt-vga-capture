# Hardware-in-the-loop check passes on fpga-4

Date: 2026-11-23. First run of `vgacap/tools/hil.py` (Milestone 5 Task 6)
against a real board: fpga-4 (pi-sw2-p35, USB serial a2961e5cac65b25f,
Tiny Tapeout demo board v3, RP2350, MicroPython b006887db6), lent by the
`tt-harness-fpga-vga` session while fpga-1 had another client connected.

```
tt-vga-testpatterns/tools/upload.py http://127.0.0.1:18035 \
    bitstreams/tt_um_vgacal_bars.bin --enable --clock-hz 500000
vgacap/tools/hil.sh --board fpga-4 --link ws://127.0.0.1:18035/serial \
    --design tt_um_vgacal_bars --clock-hz 500000 docs/results/
```

All nine checks passed (`report.md`, `run.log`): a 10 s capture of
4,898,816 samples with no overruns, 11 frames reconstructed with no
glitches, frame 5 **pixel-identical** (307,200 pixels) to the bars
reference render, a demo of 43 PNGs and an 8.6 s MKV at the requested
5 fps, 42 MJPEG parts served, and a SIGTERM stop in 0.28 s with no orphaned
process. The board answered normally afterwards.

The first attempt failed before any data moved, and the fault was ours:
`ttcap capture --design` asked the SDK to enable the design by name, and a
bitstream uploaded through the `fpgas-tt` daemon is loaded
(`tt.shuttle.enabled` was `<FPGA BitStream tt_um_vgacal_bars>`) but is not
one of the SDK's shuttle entries. `ttcap` now accepts a design that is
already enabled (vgacap `e2ed6d0`); the run above is from that commit.
