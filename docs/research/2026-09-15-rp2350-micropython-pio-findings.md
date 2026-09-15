# What the RP2350 demo board's MicroPython actually does with PIO, DMA and IRQs

Date: 2026-09-15. Board: fpga-1 (pi-sw2-p33), TT demo board v3, RP2350B,
MicroPython 1.29.0-preview `b006887db6` (2026-08-11), ttboard SDK 3.1.0.
Everything below was measured through the debug bridge with
`tools/tt_repl_probe.py` (snippets in `tmp/heaplock_test*.py` at the time)
and `tools/tt_capture_smoke.py`. Each item contradicted an assumption in
the Milestone 3 plan or its review, so they are recorded with evidence.

## 1. `PIO.gpio_base(16)` cannot be called; PIO1/PIO2 already have base 16

`rp2.PIO(n).gpio_base(16)` raised `OSError: [Errno 22] EINVAL` for n = 0,
1 and 2. MicroPython maps a non-OK return of the sdk's `pio_set_gpio_base`
to EINVAL, and `pio_set_gpio_base_unsafe` refuses when the block's
instruction memory is in use. PIO0 holds the firmware's FPGA-loader
program ("Configuring PIO with frequency: 16000000 Hz" during
`tt.shuttle[...].enable()`). `rp2.PIO(i).gpio_base()` returned
`Pin(GPIO0)`, `Pin(GPIO16)`, `Pin(GPIO16)` for i = 0, 1, 2, and the PIO1
GPIOBASE register read 0x10. Rule: use PIO1 (or PIO2), and only call
`gpio_base(16)` if the current base differs.

## 2. The GPIO base must be set for real, after clearing the block

Correction of the first version of this note: the `Pin(GPIO16)` that
`gpio_base()` reported earlier was stale; after a power cycle PIO1
reported `Pin(GPIO0)`, and every capture made while the hardware base was
0 read the static `ui_in` pins (constant 0x01). The sequence that works:
`rp2.PIO(1).remove_program()` (no argument removes every MicroPython
managed program on the block), then `rp2.PIO(1).gpio_base(16)`, which
then succeeds. With the base genuinely at 16, `in_base=machine.Pin(33)`
(the ABSOLUTE GPIO; MicroPython subtracts the base, PINCTRL IN_BASE reads
17) delivers the test pattern's bar values 0x88, 0x99, 0xaa, 0xbb, 0xcc,
0xdd, 0xee, 0xff. `in_base=Pin(17)` reads GPIO17 (constant 0x01). With
the base at 0, `Pin(33)` is invalid for the sdk and silently leaves
PINCTRL at 0.

## 3. `wait gpio` needs the absolute GPIO number on this build

With the base at 16, `wait(1, gpio, 16)` runs and `wait(1, gpio, 0)`
stalls; the stalled instruction reads back as 0x2010 (`wait 0 gpio 16`),
so the loader relocates gpio-wait indices by the base and the hardware
adds the base again: 0 becomes GPIO32, 16 wraps to GPIO16. Pin-relative
`wait(1, pin, k)` does not wrap modulo 32 inside the window either. On
RP2040 (base 0) absolute and relative coincide.

## 4. The project clock pin must not be reconfigured

`machine.Pin(16, machine.Pin.IN)` switched the clock pad away from the
firmware's PWM: GPIO16 read 0 in 200 samples afterwards, and
`tt.clock_project_PWM(500000)` did not restore it (it reuses its PWM
object). Only a board reset (`machine.reset()`) or power cycle brought
the clock back (then 101 of 200 samples high). PIO samples pad inputs
regardless of the pad's function, so leave the clock pin alone.

## 5. Hard IRQ handlers must be module-level functions

Under `micropython.heap_lock()`:

| statement | result |
|---|---|
| `mem32[precomputed_big_addr]` read | ok |
| `mem32[precomputed_big_addr] = small` write | ok |
| `big_addr + 4` | MemoryError |
| `lst[0] += 1`, `lst[0] = True` | ok |
| `uctypes.struct` field read/write | ok |
| handler body as a nested closure over locals | MemoryError at the first statement |
| same body as a module-level function over globals | ok |

Driven by a real `rp2.DMA` memory-to-memory transfer with
`irq(handler, hard=True)`, the module-level handler ran, set its flag and
re-armed `WRITE_ADDR`/`TRANS_COUNT` (+0x04 / +0x08) correctly. The
nested-closure version of `capture_rp2.py` produced "Uncaught exception in
IRQ callback handler / MemoryError" on every DMA completion and wedged the
REPL (recovered by power cycling fpga-1). Addresses at or above 2^30
(the DMA block at 0x50000000) are heap objects on this 31-bit-small-int
build, so any arithmetic on them inside a handler allocates; the negative
address idiom does not help because the magnitude is still above 2^30.

## 6. USB CDC throughput

See `2026-09-15-usb-cdc-throughput.md`: ~150 KB/s on the RP2040 board's
v1.24 firmware, ~650-740 KB/s on this board; 32 KB blocks fail to
allocate on the RP2040 board.

## Recovery notes

Two power cycles of fpga-1 today (PoE toggle via `tools/tt_power_cycle.py`,
back in about 60 s). The capture script now cleans up on Ctrl-C and emits
a final TIME chunk (`overruns=0 rxstall=0 sysclk_hz=133000000`) when the
sampler is otherwise idle.
