# tt08 `tt_um_rejunity_vga_logo`: a capture that only glitch tolerance could read

Date: 2026-09-15. Board: tt08 silicon on pi-sw2-p8, captured earlier the
same day at a 60 kHz project clock over direct serial
(`../2026-09-15-ttcap-capture-serial-tt08-glyph-mode/tiny-logo-capture.vgacap.gz`,
kept as the regression fixture).

Before Milestone 5 Task 1 this stream reconstructed **no frames at all**:

```
frame 0: 800x79 mode=? cpl=800 lpf=526 hsync=pos vsync=pos partial=1
frames=0
```

Its hsync carries occasional spurious pulses, 2 to 30 clocks wide, a few
per frame. The timing learner counted each one as a line start, so the line
count drifted, no mode matched and the picture was never assembled. Real
silicon does this; the capture path had recorded it faithfully.

With the learner rejecting pulses that do not match the learned width and
spacing:

```
frame 0: 640x480 mode=640x480@60 cpl=800 lpf=525 hsync=pos vsync=pos partial=0 glitches=19
frames=1 glitches_total=19
```

![frame 0](frame-0000.png)

The Tiny Tapeout logo over a vertical gradient, dithered, which is what the
design draws with six bits of colour. 19 spurious pulses were rejected and
counted rather than silently absorbed, so a capture that needed tolerance
says so.

This picture is now pinned as a regression test in `vgacap`
(`python/tests/test_frames_hardware_capture.py`): shape, palette, the
gradient, logo-versus-background contrast, the ring's column span and two
exact pixels, chosen so that a one-row or four-pixel shift fails the test.
