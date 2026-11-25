# tt-vga-capture

The tracking repository for [vgacap](https://github.com/mithro/vgacap),
which captures the VGA output of [Tiny Tapeout](https://tinytapeout.com)
designs and turns it into pictures and video.

This repository holds the design, research, measurements, results, work
log and task list. The code lives in sibling repositories:

- [`mithro/vgacap`](https://github.com/mithro/vgacap): the shared stream
  format and reconstruction library, every capture source (demo board
  programs and firmware, Raspberry Pi 5, FPGA), the GStreamer plugin and
  the Python tools.
- [`mithro/tt-vga-testpatterns`](https://github.com/mithro/tt-vga-testpatterns):
  Verilog calibration designs for Tiny Tapeout demo boards with an FPGA breakout.

> **Caution: AI in use.** This project is being built with [Claude Code](https://claude.com/claude-code).
> Check the design notes, measurements and code before relying on them.

## Where things are

| path | contents |
|---|---|
| [`docs/superpowers/specs/`](docs/superpowers/specs/) | approved design |
| [`docs/superpowers/plans/`](docs/superpowers/plans/) | implementation plans |
| [`docs/design/`](docs/design/) | design notes |
| [`docs/research/`](docs/research/) | research findings |
| [`docs/results/`](docs/results/) | capture results |
| [`LOG.md`](LOG.md) | dated work journal |
| [`TASKS.md`](TASKS.md) | live task list |

## License

Apache-2.0, see [LICENSE](LICENSE).
