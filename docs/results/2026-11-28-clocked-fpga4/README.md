# Clocked capture from reset on fpga-4

Date: 2026-11-28 (+1030); batches a, b and b2 ran on 2026-11-27 UTC, c and kk on 2026-11-28 UTC.
Code: vgacap branch `clocked` ([mithro/vgacap#95](https://github.com/mithro/vgacap/pull/95)).

| Batch | vgacap commit |
|---|---|
| a, b, b2 | fc65c91 |
| c, kk | eb4ccb8 |

`git diff fc65c91 eb4ccb8 -- python/ttcap/mp` is empty, so the board body is the same in every batch. The host-side change between the two commits is the read floor (40 ns at fc65c91, 80 ns at eb4ccb8) and the too-fast rule. Nothing was flashed.

`ttcap capture --mode clocked` loads the bitstream with the clock and reset held. The board's PIO then makes the project clock and reads `uo_out` once per clock, so sample k is the design's output after rising edge k, counted from reset. Each capture here was placed in the [tt-harness-fpga-vga](https://github.com/mithro/tt-harness-fpga-vga) RTL reference for fpga-4 and compared exactly over the overlap ([`analyse.py`](analyse.py)).

## Board

| Board | Pi | USB serial | Firmware | SDK | sysclk |
|---|---|---|---|---|---|
| fpga-4 | pi-sw2-p35 | `a2961e5cac65b25f` | MicroPython 970468103d | 3.1.1 (d485c7a) | 133 MHz |

## Designs

| Design | Bitstream bytes | Reference |
|---|---|---|
| `ttsky26c/tt_um_vga_ca` | 104,090 | RTL, reset from clock 0 |
| `ttsky26b/tt_um_KK_VGA01` | 104,090 | RTL, reset from clock 0 |

## Claims

Each batch had its own claim from the fpgas.online broker. Each was taken at 0 clients with `idle_display` loaded ([`status-*.json`](status-a.json)), and released.

| Batch | Claim |
|---|---|
| a | `c-EzoxmSqF_8HQ` |
| b | `c-sh3hJMhsKCXo` |
| b2 | `c-saJ6HkhFtm_1` |
| c | `c-_SKPHKbw632t` |
| kk | `c-4gK_5eWpzuqS` |

## How each batch ran

[`clocked_batch.py`](clocked_batch.py) ran on the Pi, and [`pi_setup.py`](pi_setup.py) set it up there from `git archive` of the named commit.

1. The bridge was stopped only through `pi_helper.py stop-if-idle`, which reads 0 clients three times.
2. Before the first run, the board's state was read over the raw REPL: the root listing, whether `/_vgacap` exists, `tt.mode`, the manual-clock monitor, and `rst_n`.
3. After every run the same state was read again. The first four must equal the state before, and `rst_n` must read 1.
4. At the end: `restart_sdk`, the bridge started, and `idle_display` loaded.

Every post-run state in every batch equalled the state before, with `rst_n` released ([`results_*.json`](results_a.json)). Every batch ended `RESULT PASS`. After the last batch the Pi's home listing was the same as before the first ([`teardown.log`](teardown.log)).

## Results

| Batch | Design | Runs | Result |
|---|---|---|---|
| a | vga_ca | 4, 8 and 12 clocks; 3 × 4,194,304 clocks at 500 kHz | exact |
| b | vga_ca | `--clock-high` 0..15 at 500 kHz, divider 14 | exact |
| b2 | vga_ca | `--clock-high` 0..15 at 7 MHz, divider 1 | H 0..6 wrong; H 7..15 exact |
| c | vga_ca | the fastest clock; a killed host; the bridge | exact |
| kk | KK_VGA01 | 500 kHz; the fastest clock | exact to clock 2,841,130, then 84 clocks differ |

### a: clock counts and long runs ([`batch-a.log`](batch-a.log), [`analyse-a.log`](analyse-a.log))

| Run | Clocks | Reset clocks | Method | First reference clock | Compared | Differ |
|---|---|---|---|---|---|---|
| n4 | 4 | 1 | by hand | 9 | 4 | 0 |
| n8 | 8 | 1 | by hand | 9 | 7 | 0 |
| n12 | 12 | 10 | by hand | 0 | 12 | 0 |
| big0 | 4,194,304 | 10 | `locate_capture` | 0 | 4,194,304 | 0 |
| big1 | 4,194,304 | 10 | `locate_capture` | 0 | 4,194,304 | 0 |
| big2 | 4,194,304 | 10 | `locate_capture` | 0 | 4,194,304 | 0 |

- The clock was 500 kHz exactly: divider 14, 19 cycles per clock, H 8, L 7.
- The short runs are under `locate_capture`'s 4,096-clock anchor. Their samples were compared by hand with the reference's first 16 clocks, which `analyse-a.log` prints. n8's last sample falls at reference clock 16, which is not printed, so 7 of its 8 were compared.
- The reference resets for 10 clocks, so a run with 1 reset clock starts 9 clocks earlier in the design's life. That is the shift of 9.
- The three long runs have identical samples (uo_out sha256 prefix `4248775f5bae2d2f`).
- Each long run reported `overruns=0` and `stalled_buffers=255`. That is the number of buffers during which the link held the clock, which does not lose samples.

### b and b2: the read point ([`batch-b2.log`](batch-b2.log), [`analyse-b2.log`](analyse-b2.log), [`shiftcheck.log`](shiftcheck.log))

`uo_out` is read H + 1 PIO cycles after the rising edge that the state machine drives (the read time). The GPIO input synchroniser adds 2 system clocks, so the pin level read is 15 ns earlier at 133 MHz (the pin time).

- In batch b (divider 14), every H read at least 105 ns late, and all 16 captures were exact with the same samples.
- Batch b2 used divider 1, 7 MHz, 19 cycles per clock, 400,000 clocks each:

| H | Read time | Pin time | Placed | Shift 0 differ | Shift 1 differ |
|---|---|---|---|---|---|
| 0 | 7.5 ns | before the edge | no | 30,845 | 0 |
| 1-4 | 15.0-37.6 ns | 0-22.6 ns | no | — | — |
| 5 | 45.1 ns | 30.1 ns | no | 29,843 | 1,002 |
| 6 | 52.6 ns | 37.6 ns | no | 24,351 | 30,844 |
| 7 | 60.2 ns | 45.1 ns | clock 0 | 0 | 30,844 |
| 8-15 | 67.7-120.3 ns | 52.6-105.3 ns | clock 0 | 0 | — |

- "Shift s differ" compares capture sample k + s with reference clock k, over the whole capture ([`shiftcheck.py`](shiftcheck.py)).
- H 0 reads exactly the previous clock's output. H 1-4 give the same samples as H 0.
- H 7..15 give the same samples as batch b (sha256 prefix `f85406bff1bf10a0`).

So for this design on this board the output changes between 45 and 60 ns of read time, or 30 and 45 ns of pin time, after the edge. vgacap now reads at least 80 ns of read time after the edge by default. A design with a longer clock-to-output path needs more, and `--clock-high` sets it per run ([mithro/vgacap#97](https://github.com/mithro/vgacap/issues/97) asks for a value in ns).

Before this, the 40 ns default came from the design note, not from a run. Frame mode found a 20-30 ns threshold for the tt09 bars design, with a 25 MHz project clock at sysclk 100 MHz ([2026-11-24-frame-capture-fpga4](../2026-11-24-frame-capture-fpga4/README.md)).

### c: the fastest clock, a killed host, and the bridge ([`batch-c.log`](batch-c.log), [`analyse-c.log`](analyse-c.log))

| Run | Link | Clock | Divider, H, L | Samples | Compared | Differ |
|---|---|---|---|---|---|---|
| max | serial | 9,500,000 Hz | 1, 10, 0 | 4,194,304 | 4,194,304 | 0 |
| killed | serial | 500,000 Hz | 14, 8, 7 | 2,834,432 | 2,834,432 | 0 |
| bridge | WebSocket | 500,000 Hz | 14, 8, 7 | 4,194,304 | 4,194,304 | 0 |

- **max:** the batch read `machine.freq()` (133,000,000) and asked for ceil(133,000,000 / 14) Hz, the fastest clock with an 80 ns read. 5.08 s on the board, `overruns=0`. Its samples are identical to batch a's.
- **killed:** the host was sent `SIGKILL` 12 s after start, during streaming. After a 40 s wait the board's state equalled the state before. The file has no closing record, as expected, and every sample in it is exact.
- **bridge:** the bridge was running, and the capture went through `ws://127.0.0.1:8765/serial` on the Pi. `overruns=0`, and the samples are identical to batch a's.

### kk: the design from vgacap#73 ([`batch-kk.log`](batch-kk.log), [`analyse-kk.log`](analyse-kk.log), [`kkruns.log`](kkruns.log), [`kkmodels.log`](kkmodels.log))

`tt_um_KK_VGA01` resets its game state only on a vsync edge while `rst_n` is low ([mithro/vgacap#73](https://github.com/mithro/vgacap/issues/73)). Before clocked mode, its captures differed from frame 1, at clock 420,811.

| Run | Clock | Compared | Exact to clock | Differ |
|---|---|---|---|---|
| 500k | 500,000 Hz | 4,194,304 | 2,841,129 | 84 |
| max | 9,500,000 Hz | 4,194,304 | 2,841,129 | 84 |

- The two captures are identical (sha256 prefix `09239a7e5ed4cb43`). The game now resets.
- The 84 clocks are at the left and right edges of one object on lines 401-407, in frames 6 to 9 ([`kkruns.log`](kkruns.log)):

| Frame | Left edge column | Right edge column | Edge width | Clocks |
|---|---|---|---|---|
| 6 | 330 | 337 | 1 | 14 |
| 7 | 331 | 338 | 1 | 14 |
| 8 | 331 | 338 | 2 | 28 |
| 9 | 332 | 339 | 2 | 28 |

- The RTL simulation and the FPGA build's synthesised netlist, both reset from clock 0, differ from the capture at the same 84 clocks ([`kkmodels.log`](kkmodels.log)). So the difference is neither a synthesis difference nor reset.
- It is not explained. [mithro/vgacap#96](https://github.com/mithro/vgacap/issues/96) tracks it, with an unchecked hypothesis.

## Not measured

- a fractional PIO divider;
- a system clock other than 133 MHz;
- the teardown order after a stop with the clock high, on hardware;
- designs other than these two.

## Files

| File | What |
|---|---|
| [`batch-a.log`](batch-a.log) | batch a run log |
| [`batch-b.log`](batch-b.log) | batch b run log |
| [`batch-b2.log`](batch-b2.log) | batch b2 run log |
| [`batch-c.log`](batch-c.log) | batch c run log |
| [`batch-kk.log`](batch-kk.log) | kk setup, run log and teardown |
| [`results_a.json`](results_a.json) | batch a post-run states |
| [`results_b.json`](results_b.json) | batch b post-run states |
| [`results_b2.json`](results_b2.json) | batch b2 post-run states |
| [`results_c.json`](results_c.json) | batch c post-run states |
| [`results_kk.json`](results_kk.json) | kk post-run states |
| [`analyse-a.log`](analyse-a.log) | batch a placement and comparison |
| [`analyse-b.log`](analyse-b.log) | batch b placement and comparison |
| [`analyse-b2.log`](analyse-b2.log) | batch b2 placement and comparison |
| [`analyse-c.log`](analyse-c.log) | batch c placement and comparison |
| [`analyse-kk.log`](analyse-kk.log) | kk placement and comparison |
| [`shiftcheck.log`](shiftcheck.log) | b2 shift comparison |
| [`kkdiff.log`](kkdiff.log) | kk differing clocks |
| [`kkruns.log`](kkruns.log) | kk differing runs per frame |
| [`kkmodels.log`](kkmodels.log) | kk against the RTL and netlist runs |
| [`status-a.json`](status-a.json) | board status before batch a |
| [`status-b.json`](status-b.json) | board status before batch b |
| [`status-b2.json`](status-b2.json) | board status before batch b2 |
| [`status-c.json`](status-c.json) | board status before batch c |
| [`status-c-after.json`](status-c-after.json) | board status after batch c |
| [`status-kk.json`](status-kk.json) | board status before kk |
| [`update-c.log`](update-c.log) | the Pi tree moved to eb4ccb8 |
| [`teardown.log`](teardown.log) | the Pi directory removed; home listing |
| [`clocked_batch.py`](clocked_batch.py) | the batch runner, on the Pi |
| [`pi_setup.py`](pi_setup.py) | setup, update, batch and teardown, from the host |
| [`analyse.py`](analyse.py) | placement and comparison |
| [`shiftcheck.py`](shiftcheck.py) | the shift comparison |
| [`kkdiff.py`](kkdiff.py) | the differing clocks |
| [`kkruns.py`](kkruns.py) | the differing runs |
| [`kkmodels.py`](kkmodels.py) | the model comparison |

In the logs, `HOST` stands for the host's working directory, `TT` for its checkout root, and `BITSTREAMS` for its bitstream store.
