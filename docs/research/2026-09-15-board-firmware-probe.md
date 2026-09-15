# Firmware probe of the Welland boards over the debug bridge

Date: 2026-09-15. Tool: `tools/tt_repl_probe.py` (raw-REPL over the
`fpgas-tt` WebSocket bridge, reached through an SSH tunnel to `tweed`).
This is the debug/test path; captures will own the serial device on the Pi.

## tt07 (pi-sw2-p7, RP2040 demo board)

```
MicroPython v1.24.0 on 2024-10-25, machine='Raspberry Pi Pico with RP2040'
rp2: DMA True, PIO True, StateMachine True
machine.freq() = 133000000
gc: mem_free 84864, mem_alloc 148800     (after gc.collect(), firmware idle)
ttboard 2.0.4
GPIOMap.all(): rp_projclk 0, nprojectrst 1, cinc 2, ncrst 3, cena 4,
  uo_out0..3 = 5,6,7,8, ui_in0..3 = 9,10,11,12, uo_out4..7 = 13,14,15,16,
  ui_in4..7 = 17..20, uio0..7 = 21..28, rpio29 29
tt.shuttle.run = tt07
```

Consequences:
- `rp2.DMA` exists, so a pure-MicroPython capture (PIO + DMA into a
  `bytearray`) is possible without reflashing.
- Only ~85 KB of MicroPython heap is free with the stock firmware loaded.
  A capture buffer in Python must stay well under that (say 32-64 KB), which
  is 40-80 lines of 800 clocks at one byte per clock, or 4-8 lines at the
  two-samples-per-word 12-bit layout. Whole-frame capture on the RP2040
  needs the C firmware (264 KB SRAM, no MicroPython heap in the way).
- System clock 133 MHz: the `wait 0 pin; wait 1 pin; in pins` loop (3
  instructions) samples up to ~44 MHz project clocks in principle; the
  practical limit is what the FIFO/DMA drains.
- The control lines are reported as `cinc 2, ncrst 3` (the board object
  applies the tt07 carrier-board swap), so read the map from the board
  rather than the source file.

## fpga-1 (pi-sw2-p33, RP2350 demo board v3 + FabricFox)

```
MicroPython b006887db6 on 2026-08-11 (1.29.0-preview), machine='TinyTapeout RP2350B Core with RP2350', _thread='unsafe'
rp2: DMA True, PIO True, StateMachine True
machine.freq() = 133000000
gc: mem_free 426688, mem_alloc 60992
ttboard 3.1.0
GPIOMap.all(): rp_projclk 16, manual_project_clock 15, nprojectrst 14,
  cena 0, ncrst 1, cinc 2, mng00..07 = 3..10, rp_led 11,
  analog_current_source 12, ui_in0..7 = 17..24, uio0..7 = 25..32,
  uo_out0..7 = 33..40, adc1..5 = 41..45
tt.shuttle.run = FPGA
```

Consequences:
- ~417 KB of heap free: a whole 640x480 frame with blanking (420,000
  samples at one byte per clock) does not quite fit; the active area
  (307,200) or a frame with the horizontal blanking dropped does. RP2350
  runs at 133 MHz here too (not 150 MHz).
- uo_out on GPIO 33..40 is above the RP2350 PIO's default 32-pin window:
  MicroPython's `rp2.PIO(n).gpio_base(16)` (MicroPython 1.24+) selects the
  upper window. Must be set before the state machine is created.
