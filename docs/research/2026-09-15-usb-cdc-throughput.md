# USB CDC throughput of the stock MicroPython firmware (Welland boards)

Date: 2026-09-15. Tool: `uv run --no-sync ttcap throughput <link> --bytes N --block B`
(`vgacap` 5893c61) run **on the Pi that owns the board**. The MicroPython
script writes a repeating 255-byte pattern to `sys.stdout.buffer` in
`block`-sized writes; the host counts bytes, checks every byte, and times
the transfer from the raw-REPL `OK` to the last byte. "bridge" = through
the `fpgas-tt` WebSocket bridge on `127.0.0.1:8765`; "serial" = pyserial
on `/dev/ttboard` with `fpgas-tt` stopped for the run and restarted after.

| board | MCU / firmware | link | bytes | block | seconds | KB/s | corrupt |
|---|---|---|---|---|---|---|---|
| tt07 (pi-sw2-p7, Pi 3B+) | RP2040, MicroPython v1.24.0, ttboard 2.0.4 | bridge | 1,000,000 | 32768 | — | — | MemoryError allocating 32769 bytes on the board |
| tt07 | RP2040 | bridge | 1,000,000 | 4096 | 6.518 | 149.8 | no |
| tt07 | RP2040 | bridge | 1,000,000 | 8192 | 6.539 | 149.3 | no |
| tt07 | RP2040 | serial | 1,000,000 | 4096 | 6.500 | 150.2 | no |
| tt07 | RP2040 | serial | 8,000,000 | 4096 | 50.895 | 153.5 | no |
| tt07 | RP2040 | serial | 8,000,000 | 16384 | 59.645 | 131.0 | no |
| fpga-1 (pi-sw2-p33, Pi 4) | RP2350, MicroPython 1.29.0-preview (b006887db6), ttboard 3.1.0 | bridge | 1,000,000 | 4096 | 1.460 | 668.7 | no |
| fpga-1 | RP2350 | serial | 1,000,000 | 4096 | 1.509 | 647.1 | no |
| fpga-1 | RP2350 | serial | 8,000,000 | 4096 | 11.674 | 669.2 | no |
| fpga-1 | RP2350 | serial | 8,000,000 | 32768 | 10.510 | 743.3 | no |

## Reading the numbers

- The bridge is not the bottleneck: bridge and direct serial give the same
  rate on both boards. The limit is the board's MicroPython `stdout` write
  path over USB CDC (TinyUSB), which is ~150 KB/s on the RP2040 board's
  v1.24 firmware and ~650-740 KB/s on the RP2350 board's 1.29-preview
  firmware. Whether the difference is the MicroPython version, the USB
  stack configuration or the chip is not yet separated; it can be tested
  later by flashing a newer MicroPython on an RP2040 board.
- Larger blocks do not help on the RP2040 (16 KB was slower, 32 KB did not
  allocate: the free heap is ~85 KB and fragmented); 4 KB is the default.
- No corruption in 34 MB transferred.

## Derived capture limits (Milestone 3, MicroPython prototype)

| board | bytes per sample | max samples/s | max project clock | 640x480 frame (420,000 clocks) |
|---|---|---|---|---|
| RP2040 (12-bit, 2 per word) | 2 | ~75 k | ~75 kHz | ~5.6 s |
| RP2350 (8-bit, 4 per word) | 1 | ~650 k | ~650 kHz | ~0.65 s |

Use ~60 kHz on tt07 and ~500 kHz on fpga-1 for the first captures to keep
a margin for chunk headers and the DMA/Python loop. These are slow-clock
streaming numbers for the pure-MicroPython path; whole-frame capture into
SRAM (RP2350: 417 KB heap free) and the C firmware (Milestone 7) lift
them.
