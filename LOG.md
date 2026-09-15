# Work log

Newest entries at the top. Dates are ISO 8601.

## 2026-09-15

- Brainstormed the project with Tim. Decisions recorded in
  `docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md`. Key points:
  three repos (`tt-vga-capture`, `vgacap`, `tt-vga-testpatterns`); all
  capture modes are wanted, simplest first; both external-clock and
  self-clocked sampling; multiple stream encodings allowed when justified;
  the Welland WebSocket bridge is for debugging only, real captures own
  the serial device on the Pi; whole-frame capture into RP2 SRAM is a
  first-class mode; never blame the hardware.
- Surveyed Welland: tt03p5-tt08 are RP2040 demo boards on switch 2 ports
  3-8; fpga-1..4 are RP2350 demo boards v3 with the FabricFox iCE40UP5K
  breakout on ports 33-36. `ten64` and `tweed` accept SSH; `tweed`'s host
  key had changed after its rebuild and was verified via `ten64` before
  updating `~/.ssh/known_hosts`. The Pis refused user `tim`.
- Extracted the RP2040 and RP2350 GPIO maps from the Tiny Tapeout
  MicroPython firmware (v2.0.4 `GPIOMapTT06`, v3.x `GPIOMapTTDBv3`): uo_out
  is not contiguous on RP2040 boards.
- Listed silicon-tested VGA projects on the Welland shuttles from the
  project-search database; candidates for the first capture: tt07 VGA
  Checkers, tt08 VGA Tiny Logo, tt08 Glyph Mode.
- Started local tooling: pico-sdk and oss-cad-suite into `~/tools/`.
