# tt-vga-capture

Tracking repository for capturing the Tiny VGA Pmod output of Tiny Tapeout
projects with the PIO block of the demo board's RP2040 / RP2350 (later the
Raspberry Pi 5 RP1 and bunnie's BIO), reconstructing the picture on a host,
and presenting it as a virtual video source through GStreamer.

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

- [`mithro/vgacap`](https://github.com/mithro/vgacap): the C libraries
  (stream formats, reconstruction, RP2 and RP1 capture), the GStreamer
  plugin and the Python tools.
- [`mithro/tt-vga-testpatterns`](https://github.com/mithro/tt-vga-testpatterns):
  Verilog calibration designs for the Tiny Tapeout FPGA emulation boards.

## License

Apache-2.0, see [LICENSE](LICENSE).
