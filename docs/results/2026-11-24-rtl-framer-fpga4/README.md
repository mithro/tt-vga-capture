# vgacap's RTL framer works on a real FPGA, at 250 kHz and at 25 MHz

Date: 2026-11-24. Board: fpga-4 (sw2 p35, USB serial a2961e5cac65b25f,
Tiny Tapeout demo board v3, RP2350, SDK 3.1.0, FabricFox iCE40UP5K). The
board was lent by the tt-harness session while its census waited on the
tinytapeout.fpgas.online certificate renewal. fpga-1 had an outside client.
Everything went over an SSH tunnel to the Pi's own daemon
(`ssh -N -L 18035:10.21.2.35:8765 tweed.welland.mithis.com`), not through
the public proxy.

## What was tested

- **Framer:** `vgacap_raw_framer`, vgacap `rtl/`, PR #4 at e1bb8c1.
- **Test design:** tt-vga-testpatterns `tt_um_vgacal_framer`, branch
  `framer-design` at 2f48eb4.
  - It feeds the bars picture into the framer, sampled every other clock.
  - `uo_out` carries the chunk bytes, and `uio[0]` marks the clocks that
    carry one.
- **Bitstream:** Debian yosys 0.52 and nextpnr-ice40 0.7.
  - 635 of 5280 LCs, 2 of 30 block RAMs.
  - Fmax 33.66 MHz against the 25 MHz target.

On the RP2350, uio[0..7] are GPIO 25..32 and uo_out[0..7] are GPIO 33..40.
So a single 16-pin PIO `in pins` from GPIO 25 sees both, phase-locked to
the project clock. `hil_framer.py` runs two checks with that sampler:

- **logic.** ttcap's ordinary streaming capture with a 16-bit profile, at
  250 kHz (500 KB/s, lossless).
  - It captures 499,712 clocks with 0 overruns and rxstall 0.
  - The bytes marked valid are parsed as vgacap chunks: only `RAW ` chunks,
    with no overrun `TIME` chunk.
  - The 249,600 framer samples, 1.19 frames of every-other-clock samples,
    are the bars picture exactly.
- **speed.** At the design's real 25 MHz.
  - A one-shot board program fills 16K–32K words of RAM by DMA with the
    same sampler (32,768–65,536 consecutive clocks), then prints them as
    base64.
  - Every framer chunk in the window is bars samples.
  - Consecutive chunks form one run exactly 512 clocks apart in the
    picture, so not a single sample was lost or repeated inside the
    window.

## Results (`hil_framer.log`)

The last sequence, run back to back without a restart, all passed:

| run | result |
|---|---|
| logic, 250 kHz | 249,600 samples are the bars picture |
| logic, 250 kHz | 249,600 samples are the bars picture |
| speed, 25 MHz | 63 chunks, one contiguous run |
| logic, 250 kHz | 249,600 samples are the bars picture |
| speed, 25 MHz | 63 chunks, one contiguous run |

Two earlier 25 MHz windows of 32K words each gave 127 chunks, one
contiguous run each.

## Faults found on the way (all ours)

- **No block RAM.** The first framer used an asynchronous-read FIFO. That
  can't be block RAM, so it became flip-flops: 157% of the LCs, and
  placement failed. Fixed in vgacap with a synchronous-read FIFO plus a
  prefetch. The output still carries one byte a clock.
- **25 MHz timing.** It failed at 21 MHz until `hpos / 10` became counters
  and the picture byte and outputs were registered. These changes are in
  the test design only; the framer itself was fine.
- **Parser.** `build.py` didn't read yosys 0.52's `name count` cell lines.
  Fixed on the same branch.
- **Clock never started.** `hil_framer.py` didn't start the project clock
  (`select_project()`, as `ttcap capture` does). Its first capture used the
  clock the daemon had left running. Its own `stop_clock()` then made every
  later capture wait for edges that never came, which looked like "board
  went quiet". Stock `ttcap capture` ran fine back to back the whole time.
- **Heap fragmentation.** After a capture's compile, the heap's largest
  block can be under 128 KB, so the window halves itself until it fits.
- **RXSTALL in the window program is always 1, and that's expected.** The
  state machine keeps sampling after the DMA count is reached, so the FIFO
  fills before the poll loop can stop it. Integrity comes from the chunk
  chain instead.

## Expected ambiguity in the reported offsets

The speed check reports offsets like `[31872, 31873, 32672]`. With samples
every other clock, the bars picture can't tell offset k from k+1, because
every bar edge and sync edge sits at an even pixel. And vertical blanking
repeats the same line, so 800 clocks later also fits. Neither can hide a
lost or duplicated sample: that would break the framer's byte stream.

Afterwards the board was restored: SDK restarted, idle display `loaded`,
claim removed.
