# tt-vga-capture

The tracking repository for capturing the VGA output of
[Tiny Tapeout](https://tinytapeout.com) designs (the `uo_out` pins that
drive the [Tiny VGA Pmod](https://github.com/mole99/tiny-vga)) and turning
it into pictures and video. The captures come from several capture sources
(the Tiny Tapeout demo board's RP2040 or RP2350 microcontroller, a
Raspberry Pi 5, an FPGA design, simulators), which all write one stream
format, the [vgacap stream](docs/research/2026-09-15-stream-format.md).
Shared tools reconstruct the frames from it, check them pixel by pixel and
play them through [GStreamer](https://gstreamer.freedesktop.org).

This repository holds the design, research, measurements, results, work
log and task list. The code lives in sibling repositories:

- [`mithro/vgacap`](https://github.com/mithro/vgacap): the shared stream
  format and reconstruction library, every capture source (demo board
  programs and firmware, Raspberry Pi 5, FPGA), the GStreamer plugin and
  the Python tools.
- [`mithro/tt-vga-testpatterns`](https://github.com/mithro/tt-vga-testpatterns):
  Verilog calibration designs for Tiny Tapeout demo boards with an FPGA breakout.

> **Caution: AI in use.** This project is being built with Claude Code.
> Check the design notes, measurements and code before relying on them.

## Where things are

| path | contents |
|---|---|
| [`docs/superpowers/specs/`](docs/superpowers/specs/) | approved design |
| [`docs/superpowers/plans/`](docs/superpowers/plans/) | implementation plans |
| [`docs/design/`](docs/design/) | design notes |
| [`docs/research/`](docs/research/) | research findings |
| [`docs/results/`](docs/results/) | captured images and timing reports |
| [`LOG.md`](LOG.md) | dated work journal |
| [`TASKS.md`](TASKS.md) | live task list |

The research covers board wiring, measurements and format experiments, and
each result keeps the commands that produced it.

## License

Apache-2.0, see [LICENSE](LICENSE).
