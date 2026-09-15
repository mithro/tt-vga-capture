# Tiny Tapeout VGA capture: design

Date: 2026-09-15
Status: approved by Tim (brainstorm 2026-09-15), implementation starting

Capture the Tiny VGA Pmod signals of a Tiny Tapeout project with the PIO
block of the demo board's RP2 microcontroller (later the Raspberry Pi 5 RP1
and bunnie's BIO), rebuild the picture on a host, and present it as a
virtual video source through GStreamer. Verify the whole pipeline with
calibration designs running on the Tiny Tapeout FPGA emulation boards.

## 1. Goals

1. A capture library, in C, that samples the eight `uo_out` bits of a
   Tiny Tapeout project once per project clock using the RP2040 / RP2350 PIO
   on the Tiny Tapeout demo boards, and streams the samples to a host.
   Runs bare metal (pico-sdk) and as a MicroPython C module. A pure
   MicroPython loader of the same PIO programs exists for prototyping
   and for boards where the stock firmware must stay.
2. A picture reconstruction library, in C, that turns any per-clock sample
   stream (from PIO capture, from a simulator, from a file) into frames,
   detecting the video timing itself.
3. A GStreamer plugin exposing the reconstruction as `vgadecode`, capture
   sources for the Tiny Tapeout MCU and for the RP1, and a convenience bin.
4. A demo that captures a real project on the Welland boards
   (tinytapeout.fpgas.online) and produces PNG snapshots, a video file, a
   local window, and a browser-viewable stream.
5. Verilog calibration designs, built for the iCE40UP5K FPGA emulation
   boards, that make every stage of the pipeline checkable against a known
   picture.
6. Later: the same capture on the Raspberry Pi 5 RP1 (full pixel rate) and
   on bunnie's BIO (simulator first). The capture API is designed for these
   backends now; only the RP2 backend is implemented in this phase.

Everything is Apache-2.0. Core code is C99 with no dependencies beyond libc
(and pico-sdk / piolib / GStreamer where a backend or plugin needs them).
Python (via `uv`) is used for driver scripts, prototypes and exploration;
exploration scripts are committed, not thrown away.

## 2. Working principles

- **The hardware is never at fault.** When a capture looks wrong the bug is
  in this project's code, its assumptions or its measurements, until proven
  otherwise with evidence. Findings are written up in `docs/research/`.
- **Commit small and often.** Every logical change is its own commit;
  `LOG.md` and `TASKS.md` in this repo are updated and committed with every
  change so work can stop at any moment and be resumed.
- **Measure, don't guess.** Bandwidth, sample rates, FIFO depths and USB
  throughput are measured on the real boards and recorded before a design
  choice depends on them. The first estimate (25 MB/s for 640x480 at 25 MHz
  with one byte per clock) is an upper bound; real projects are lower
  resolution, 6-bit colour and highly repetitive, so compression and
  whole-frame buffering are expected to matter more than raw link speed.
- **Formats serve the pipeline, not the other way round.** Several stream
  encodings are allowed where a measurement justifies one; the decoder
  accepts all of them through one interface.
- **The Welland WebSocket bridge is for debugging and testing only.**
  High-performance capture runs on the Pi that owns the board and opens the
  serial device (or, later, the RP1) directly.
- **Sub-agents**: at most two in parallel, each on its own branch in a
  `.worktrees/` checkout of the repo it changes, never on `main`; their
  branches are reviewed before merging.

## 3. Hardware facts the design relies on

Recorded in `docs/research/2026-09-15-welland-boards-and-gpio.md`; summary:

| Board | MCU | clk | uo_out GPIOs | Notes |
|---|---|---|---|---|
| Welland tt03p5, tt04, tt05, tt06, tt07, tt08 (sw2 ports 3-8) | RP2040 | GPIO0 | 5,6,7,8, 13,14,15,16 | ui_in[0..3] on 9-12 sits in the gap; tt04 muxes uo_out[1..3] with mux control lines |
| Welland fpga-1..4 (sw2 ports 33-36) | RP2350 (demo board v3, SDK 3.1.0) | GPIO16 | 33..40 | contiguous; PIO needs `GPIOBASE=16`; FabricFox iCE40UP5K breakout |

Tiny VGA Pmod mapping: uo_out[0]=R1, [1]=G1, [2]=B1, [3]=vsync, [4]=R0,
[5]=G0, [6]=B0, [7]=hsync. Six bits of colour, 64 colours.

Each Welland Pi runs the `fpgas-tt` daemon (`:8765`): `GET /health`,
`WS /serial` (fan-out bridge to `/dev/ttboard`, the board's MicroPython
REPL), and on FPGA boards `GET /designs`, `POST /designs/<name>/enable`,
`POST /bitstream`, `POST /demos/sync`. tweed proxies these as
`https://tinytapeout.fpgas.online/ws/board/<slug>/serial` and
`/api/board/<slug>/...`. Boards and Pis may be power cycled, one at a time.

## 4. Repositories

| Repo | Purpose |
|---|---|
| `mithro/tt-vga-capture` | Tracking: this spec, plans, research notes, results, `LOG.md`, `TASKS.md`. |
| `mithro/vgacap` | All C code: stream formats, reconstruction, RP2 capture (PIO + firmware + MicroPython module + Python loader), RP1 capture, GStreamer plugin, Python tools, tests. |
| `mithro/tt-vga-testpatterns` | Calibration Verilog designs in Tiny Tapeout template form, cocotb tests, reference renderers, iCE40UP5K builds and committed bitstreams. |
| fork of `TinyTapeout/tt-micropython-firmware` | Only when the MicroPython C module milestone arrives; carries the module on a branch. |

## 5. Components

### 5.1 `vgacap/stream`: sample stream formats

One decoder interface, several encodings. A stream is a sequence of
self-describing chunks; each chunk starts with a 4-byte type tag and a
32-bit little-endian payload length.

Header chunk `VGCH` (first in every stream):
- format version;
- sample width in bits (8, 12, 16 or 32) and packing (LSB-first, as PIO
  `in` with autopush produces);
- signal map: for each of hsync, vsync, r1, r0, g1, g0, b1, b0 the sample
  bit index carrying it, or "absent"; other bits are ignored;
- nominal project clock in Hz and the sampling mode (external-edge,
  self-clocked, event);
- free-text source description (board, project, firmware, date).

Data chunk types:
- `RAW`: N packed samples, one per project clock, contiguous in time.
- `RLE`: (u32 value, u32 run length) pairs.
- `FRAM`: a whole frame or a line range of one frame: frame counter, first
  line index, line count, then samples. Produced by the whole-frame and
  windowed capture modes; the decoder places it by counter and line.
- `EVNT`: (clock timestamp, value) change events, for simulators and logic
  analysers.
- `TIME`: a timing annotation (host timestamp, project clock setting,
  dropped-sample notice) for diagnostics.

Any encoding may be added later behind the same decoder when a measurement
shows it pays off (for example a PIO-side run counter). Encoders and the
decoder are plain C with no allocation after init; a Python reader/writer
lives in `tools/` for scripts and tests.

### 5.2 `vgacap/frame`: reconstruction library (`libvgaframe`)

Input: per-clock samples from the stream decoder (any chunk type) or from a
direct `(timestamp, value)` API used by simulators.

Behaviour:
- Learns sync polarity by measuring the duty cycle of hsync and vsync.
- Measures clocks per line, lines per frame, sync widths; publishes them as
  detected timing.
- Locates active video either from a supplied mode table entry (640x480@60
  and friends, matched to the measured line and frame lengths) or, when no
  entry matches, from the extent of non-black pixels over a frame.
- Writes 6-bit colour expanded to RGB24 into a framebuffer; reports each
  completed frame through a callback with the timing metadata.
- Accumulates partial `FRAM` chunks into a persistent framebuffer with a
  per-line coverage map and emits when coverage is complete, or on a
  timeout with a "partial" flag.
- Never allocates after init; framebuffer size is bounded by a configured
  maximum resolution.

Tested with synthetic streams generated in C and Python, and with streams
produced by simulating the calibration designs in Icarus Verilog.

### 5.3 `vgacap/capture-rp2`: RP2040 / RP2350 PIO capture

PIO programs, kept as `.pio` sources shared by every build flavour:

1. `sample_extclk`: `wait 0 pin clk; wait 1 pin clk; in pins, N` with
   autopush, at full system clock. N and the input base depend on the board
   map (12 bits from GPIO5 on RP2040 boards, 8 bits from GPIO33 with
   GPIOBASE 16 on RP2350 boards). Alternative for RP2040 boards: two state
   machines with `in pins, 4` each, synchronised on the same clock edge,
   giving a packed byte per pixel across two DMA buffers.
2. `sample_selfclk`: the state machine drives the project clock with
   side-set and samples at a fixed phase; project clock comes from the
   PIO clock divider.
3. `sample_frame`: waits for the vsync edge, counts hsync edges to a start
   line, then captures a line range or the whole frame; used for
   whole-frame-to-SRAM and windowed capture.

Host-side firmware:
- DMA from the RX FIFO into ring buffers (streaming) or into one large
  buffer (whole frame). RP2350 has 520 KB of SRAM, enough for a whole
  640x480 frame including blanking at one byte per clock; RP2040 has
  264 KB, so whole-frame capture packs samples or captures halves over two
  frames. Flash is not written during capture.
- Transmit as stream chunks over USB CDC, with a small command protocol
  (start/stop, mode, clock, window) driven from the host.
- Three delivery flavours in this order: a MicroPython script (`rp2.PIO`,
  `rp2.DMA`) pushed through the REPL, which works on the stock Welland
  firmware; a pico-sdk C firmware; a MicroPython USER_C_MODULE in a fork
  of the Tiny Tapeout firmware. All three share the `.pio` sources and the
  stream encoders.

Capture modes (all kept, simplest first):
- **Slow-clock streaming**: project clock at a rate whose one-byte-per-clock
  stream fits the measured USB throughput; continuous video at a low frame
  rate.
- **Whole-frame capture**: full project clock, one frame into SRAM, then
  transmitted while frames are skipped; frame-rate decimation.
- **Windowed (stroboscopic)**: full clock, a line range per frame,
  reassembled over frames; for static or frame-periodic content and for
  the RP2040's smaller SRAM.
- **Compressed streaming**: RLE done by the CPU or by the PIO (research task
  with measurements) to raise the sustainable clock.

### 5.4 `vgacap/capture-rp1`: Raspberry Pi 5 RP1 (later)

Same `.pio` programs on the RP1 via piolib, DMA into DRAM ring buffers,
building on `mithro/rpi5-rp1-pio-bench` (cyclic DMA kernel module, 45-56
MB/s receive). Implemented when a Pi 5 is wired to a Tiny Tapeout board.
The capture API (`vgacap_backend` with open/configure/start/read/stop) is
defined now and implemented by the RP2 host-side transport first.

### 5.5 BIO backend (later)

Interface stub and a research note on the BIO simulator only. No
implementation this phase.

### 5.6 `vgacap/gst`: GStreamer plugin

- `vgadecode`: `application/x-vgacap` bytes in, `video/x-raw` RGB out;
  wraps `libvgaframe`. Properties: `repeat-last-frame` (present a steady
  rate to downstream), `mode` override, `max-width`/`max-height`.
- `vgacapttsrc`: Tiny Tapeout MCU source. `device=/dev/ttyACM0` for direct
  serial ownership on the Pi (the high-performance path), or
  `uri=wss://.../ws/board/<slug>/serial` for the debugging path; sends the
  command protocol, emits stream bytes.
- `vgacaprp1src`: RP1 source (later, same shape).
- `vgacapbin`: picks the source from a URI scheme (`tt-serial://`,
  `tt-ws://`, `rp1://`, `file://`) and links it to `vgadecode`.

### 5.7 `vgacap/tools`: Python drivers and helpers

- `ttvga-demo`: pick a Welland board and project, select the project and
  clock through the REPL, load the capture program, stream, and run a
  GStreamer pipeline writing PNGs and an MKV; options for `autovideosink`
  and for an HLS or MJPEG endpoint viewable in a browser.
- `vcd2vgacap`: VCD to `EVNT` stream.
- `vgacap-diff`: image comparison and timing report between a captured
  frame and a reference render (the same tool will compare against a USB
  VGA capture card when one is available).
- The MicroPython prototype loader.

### 5.8 `tt-vga-testpatterns`: calibration designs

Each is a Tiny Tapeout template project (`info.yaml`, `src/`,
`docs/info.md`, `test/` with cocotb) with a Python reference renderer that
produces the expected image for the same parameters.

| Design | Purpose |
|---|---|
| `tt_um_vgacal_bars` | all 64 colours in bars plus sync-polarity-independent framing |
| `tt_um_vgacal_grid` | one-pixel grid and border: sample phase and pixel alignment |
| `tt_um_vgacal_counter` | frame and line counters encoded in pixel blocks: frame ordering, windowed reassembly, dropped frames |
| `tt_um_vgacal_modes` | `ui_in` selects timing (640x480, 800x600, 720x400) and sync polarities |
| `tt_um_vgacal_prbs` | pseudo-random pixels seeded per frame: bit-error rate |

Built with `tt_fpga.py harden` (yosys, nextpnr-ice40 `--up5k --package
sg48`, FabricFox v2 pcf) using oss-cad-suite; bitstreams are committed and
uploaded to fpga-1..4 through the daemon API.

## 6. Data flow

```
TT project ──uo_out[7:0]──▶ RP2 PIO ──FIFO/DMA──▶ SRAM ──USB CDC──▶ Pi
   (or FPGA emulation)      (stream chunks)                          │
                                                                     ▼
 simulator ──VCD──▶ vcd2vgacap ──EVNT──┐                    vgacapttsrc
                                       ├──▶ vgadecode ──▶ pngenc / x264enc / autovideosink / hlssink
 RP1 PIO (later) ──▶ vgacaprp1src ─────┘        (libvgaframe)
```

## 7. Error handling

| Condition | Behaviour |
|---|---|
| FIFO overrun / DMA ring wrap on the MCU | counted, reported in a `TIME` chunk; the decoder marks the frame partial rather than guessing |
| Sync never detected | decoder reports "no sync" with the measured bit activity so a wrong signal map is obvious |
| Timing matches no mode table entry | auto-detected active area, flagged as such in metadata |
| Serial device busy (daemon owns it) | the tool says so and offers to stop `fpgas-tt` on that Pi or to use the bridge |
| Bridge disconnects | reconnect with back-off; a capture in progress is abandoned and reported |
| Board unresponsive | power cycle via the existing site control, one board at a time, logged |

## 8. Testing

| Layer | Test |
|---|---|
| stream | round-trip of every chunk type; fuzzed lengths; Python and C readers agree |
| frame | synthetic streams for each mode table entry and both polarities; iverilog streams from every calibration design compared pixel-exactly to the reference renderers; partial `FRAM` accumulation |
| capture-rp2 | PIO programs assembled and simulated on the host (pioasm output checked into the repo); hardware-in-the-loop against Welland with the calibration bitstreams on fpga-1 and the reference renders |
| gst | `gst-inspect` registration, a file-to-PNG pipeline in CI, HIL pipelines against Welland |
| testpatterns | cocotb per design; full build of every design in CI |

Every hardware result (images, timing measurements, throughput) is
committed under `docs/results/` in the tracking repo with the exact
commands used.

## 9. Order of work

1. Tracking repo, spec, plan; GitHub repos.
2. Stream formats and `libvgaframe` with synthetic tests.
3. MicroPython PIO prototype at Welland, slow-clock streaming, first real
   picture from a silicon project (candidates, silicon-tested "working":
   tt07 VGA Checkers, tt08 VGA Tiny Logo, tt08 Glyph Mode; animated
   stretch: tt05 Flappy VGA, tt08 VGA Nyan Cat, tt07 DVD Screensaver).
4. Calibration Verilog, iCE40 bitstreams on fpga-1, pixel-exact checks.
5. GStreamer plugin and the demo (PNG, MKV, window, browser stream).
6. Whole-frame and windowed capture modes.
7. pico-sdk firmware and the MicroPython C module; direct serial ownership
   on the Pi.
8. Compression research with measurements.
9. RP1 backend when hardware exists; BIO note.
