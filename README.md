# tt-vga-capture

Tracking repository for capturing the VGA output of Tiny Tapeout designs
(the Tiny VGA Pmod's `uo_out` pins) and turning it into pictures and video.
The captures come from several sources -- the Tiny Tapeout demo board's
RP2040 or RP2350 microcontroller, a Raspberry Pi 5, an FPGA design,
simulators -- all writing one stream format that shared tools reconstruct,
check pixel by pixel and play through GStreamer.

This repository holds the design, research, measurements, results, work
log and task list. The code is in [mithro/vgacap](https://github.com/mithro/vgacap).

> **Caution: AI in use.** This project is being built with Claude Code.
> Design notes, measurements and code should be checked before relying on
> them.

## Where things are

| | |
|---|---|
| [`docs/superpowers/specs/`](docs/superpowers/specs/) | the approved design |
| [`docs/superpowers/plans/`](docs/superpowers/plans/) | implementation plans |
| [`docs/research/`](docs/research/) | findings: board wiring, measurements, format experiments |
| [`docs/results/`](docs/results/) | captured images and timing reports, with the commands that produced them |
| [`LOG.md`](LOG.md) | dated work journal |
| [`TASKS.md`](TASKS.md) | live task list |

Code lives in sibling repositories:

- [`mithro/vgacap`](https://github.com/mithro/vgacap): the shared stream
  format and reconstruction library, every capture source (demo-board
  programs and firmware, Raspberry Pi 5, FPGA), the GStreamer plugin and
  the Python tools.
- [`mithro/tt-vga-testpatterns`](https://github.com/mithro/tt-vga-testpatterns):
  Verilog calibration designs for the Tiny Tapeout FPGA emulation boards.

## License

Apache-2.0, see [LICENSE](LICENSE).
