# Clocked capture from reset on fpga-4

Date: 2026-11-28 (+1030); batches a, b and b2 ran on 2026-11-27 UTC, c and kk on 2026-11-28 UTC.
Code: vgacap branch `clocked` ([mithro/vgacap#95](https://github.com/mithro/vgacap/pull/95)).

| Batch | vgacap commit |
|---|---|
| a | [fc65c91](https://github.com/mithro/vgacap/commit/fc65c91) |
| b | [fc65c91](https://github.com/mithro/vgacap/commit/fc65c91) |
| b2 | [fc65c91](https://github.com/mithro/vgacap/commit/fc65c91) |
| c | [eb4ccb8](https://github.com/mithro/vgacap/commit/eb4ccb8) |
| kk | [eb4ccb8](https://github.com/mithro/vgacap/commit/eb4ccb8) |

[`pi_setup.py`](pi_setup.py) names the commit it installs. It named fc65c91 for batches a, b and b2, and the copy here names eb4ccb8. [`update-c.log`](update-c.log) and [`batch-kk.log`](batch-kk.log) show eb4ccb8 being archived. The 40 ns warnings in [`batch-b2.log`](batch-b2.log) are fc65c91's floor.

`git diff fc65c91 eb4ccb8 -- python/ttcap/mp` is empty, so the board body is the same in every batch. Between the two commits only the host changed, in two ways:
- the read floor went from 40 ns to 80 ns;
- a `--clock-hz` above the fastest clock is now refused.

Nothing was flashed.

[`ttcap capture --mode clocked`](https://github.com/mithro/vgacap/blob/eb4ccb8/python/ttcap/how-to-capture-clocked.md) loads the bitstream with the clock and reset held. The board's PIO then makes the project clock and reads `uo_out` once per clock. So sample k is the design's output after rising edge k, counted from reset.

Each capture of 4,096 clocks or more was placed in the [tt-harness-fpga-vga](https://github.com/mithro/tt-harness-fpga-vga) RTL reference for fpga-4 and compared exactly over the overlap ([`analyse.py`](analyse.py)). The shorter ones were compared by hand (batch a, below).

## Board

| Board | Pi | USB serial | Firmware | SDK version | SDK revision | sysclk |
|---|---|---|---|---|---|---|
| fpga-4 | pi-sw2-p35 | `a2961e5cac65b25f` | MicroPython 970468103d | 3.1.1 | d485c7a | 133 MHz |

## Designs

| Design | Bitstream bytes | Bitstream sha256 prefix | Reference |
|---|---|---|---|
| `ttsky26c/tt_um_vga_ca` | 104,090 | `c388675321d9` | RTL |
| `ttsky26b/tt_um_KK_VGA01` | 104,090 | `7354ab9e6292` | RTL |

The sizes and hashes are in [`bitstreams.log`](bitstreams.log). Both references are RTL simulations reset from clock 0.

## Claims

Each batch had its own claim from the [fpgas.online](https://fpgas.online) board broker. Each was taken at 0 clients with `idle_display` loaded ([`status-a.json`](status-a.json), [`status-b.json`](status-b.json), [`status-b2.json`](status-b2.json), [`status-c.json`](status-c.json), [`status-kk.json`](status-kk.json)), and released. The claim ids are from the broker's claim and release replies, which are not kept in this folder.

| Batch | Claim |
|---|---|
| a | `c-EzoxmSqF_8HQ` |
| b | `c-sh3hJMhsKCXo` |
| b2 | `c-saJ6HkhFtm_1` |
| c | `c-_SKPHKbw632t` |
| kk | `c-4gK_5eWpzuqS` |

## How each batch ran

[`clocked_batch.py`](clocked_batch.py) ran on the Pi, and [`pi_setup.py`](pi_setup.py) set it up there from `git archive` of the named commit.

1. The bridge was stopped only through [`pi_helper.py`](https://github.com/mithro/tt-harness-fpga-vga/blob/6cf157b/scripts/hardware_library/pi_helper.py) `stop-if-idle`, which reads 0 clients three times.
2. Before the first run, the board's state was read over the raw REPL: the root listing, whether `/_vgacap` exists, `tt.mode`, the manual-clock monitor, and `rst_n`.
3. After every run the same state was read again. The first four must equal the state before, and `rst_n` must read 1.
4. At the end: [`restart_sdk`](https://github.com/mithro/vgacap/blob/eb4ccb8/python/ttcap/repl.py), the bridge started, and `idle_display` loaded.

Every post-run state in every batch equalled the state before, with `rst_n` released ([`results_a.json`](results_a.json), [`results_b.json`](results_b.json), [`results_b2.json`](results_b2.json), [`results_c.json`](results_c.json), [`results_kk.json`](results_kk.json)). Every batch ended `RESULT PASS`. The Pi's home listing was the same before the kk setup and after its teardown ([`batch-kk.log`](batch-kk.log)), and after batch c's teardown ([`teardown.log`](teardown.log)).

## Results

| Batch | Design | Runs | Exact | Not exact |
|---|---|---|---|---|
| a | `tt_um_vga_ca` | 6 | 6 | 0 |
| b | `tt_um_vga_ca` | 16 | 16 | 0 |
| b2 | `tt_um_vga_ca` | 16 | 9 | 7 |
| c | `tt_um_vga_ca` | 3 | 3 | 0 |
| kk | `tt_um_KK_VGA01` | 2 | 0 | 2 |

### a: clock counts and long runs ([`batch-a.log`](batch-a.log), [`analyse-a.log`](analyse-a.log))

| Run | Clocks | Reset clocks | Method | First reference clock | Compared | Differ |
|---|---|---|---|---|---|---|
| n4 | 4 | 1 | by hand | 9 | 4 | 0 |
| n8 | 8 | 1 | by hand | 9 | 7 | 0 |
| n12 | 12 | 10 | by hand | 0 | 12 | 0 |
| big0 | 4,194,304 | 10 | [`locate_capture`](https://github.com/mithro/tt-harness-fpga-vga/blob/6cf157b/tthfv/compare.py) | 0 | 4,194,304 | 0 |
| big1 | 4,194,304 | 10 | [`locate_capture`](https://github.com/mithro/tt-harness-fpga-vga/blob/6cf157b/tthfv/compare.py) | 0 | 4,194,304 | 0 |
| big2 | 4,194,304 | 10 | [`locate_capture`](https://github.com/mithro/tt-harness-fpga-vga/blob/6cf157b/tthfv/compare.py) | 0 | 4,194,304 | 0 |

- The clock was 500 kHz exactly: divider 14, 19 cycles per clock, H 8, L 7.
- The short runs are under [`locate_capture`](https://github.com/mithro/tt-harness-fpga-vga/blob/6cf157b/tthfv/compare.py)'s 4,096-clock anchor. Their samples were compared by hand with the reference's first 16 clocks, which `analyse-a.log` prints. n8's last sample falls at reference clock 16, which is not printed, so 7 of its 8 were compared.
- The reference resets for 10 clocks, so a run with 1 reset clock starts 9 clocks earlier in the design's life. That is the shift of 9.
- The three long runs have identical samples (uo_out sha256 prefix `4248775f5bae2d2f`).
- Each long run reported `overruns=0` and `stalled_buffers=255`. That is the number of buffers during which the link held the clock, which does not lose samples.

### b and b2: the read point ([`batch-b2.log`](batch-b2.log), [`analyse-b2.log`](analyse-b2.log), [`shiftcheck.log`](shiftcheck.log))

`uo_out` is read H + 1 PIO cycles after the rising edge that the state machine drives (the read time). The GPIO input synchroniser adds 2 system clocks, so the pin level read is 15 ns earlier at 133 MHz (the pin time).

- In batch b (divider 14), every H read at least 105 ns late, and all 16 captures were exact with the same samples.
- Batch b2 used divider 1, 7 MHz, 19 cycles per clock, 400,000 clocks each:

| H | Read time | Pin time | Samples sha256 prefix | Placed at reference clock 0 |
|---|---|---|---|---|
| 0 | 7.5 ns | -7.5 ns | `014098263572c644` | no |
| 1 | 15.0 ns | 0.0 ns | `014098263572c644` | no |
| 2 | 22.6 ns | 7.5 ns | `014098263572c644` | no |
| 3 | 30.1 ns | 15.0 ns | `014098263572c644` | no |
| 4 | 37.6 ns | 22.6 ns | `014098263572c644` | no |
| 5 | 45.1 ns | 30.1 ns | `566cacfaf1cc5418` | no |
| 6 | 52.6 ns | 37.6 ns | `9aa4e8cf6b4d49d9` | no |
| 7 | 60.2 ns | 45.1 ns | `f85406bff1bf10a0` | yes |
| 8 | 67.7 ns | 52.6 ns | `f85406bff1bf10a0` | yes |
| 9 | 75.2 ns | 60.2 ns | `f85406bff1bf10a0` | yes |
| 10 | 82.7 ns | 67.7 ns | `f85406bff1bf10a0` | yes |
| 11 | 90.2 ns | 75.2 ns | `f85406bff1bf10a0` | yes |
| 12 | 97.7 ns | 82.7 ns | `f85406bff1bf10a0` | yes |
| 13 | 105.3 ns | 90.2 ns | `f85406bff1bf10a0` | yes |
| 14 | 112.8 ns | 97.7 ns | `f85406bff1bf10a0` | yes |
| 15 | 120.3 ns | 105.3 ns | `f85406bff1bf10a0` | yes |

H 7-15 give the same samples as batch b. H 1-4 give the same samples as H 0.

[`shiftcheck.py`](shiftcheck.py) compared four captures with the reference shifted by s clocks. It compares capture sample k + s with reference clock k, over the whole capture.

| H | Differ at shift 0 | Differ at shift 1 |
|---|---|---|
| 0 | 30,845 | 0 |
| 5 | 29,843 | 1,002 |
| 6 | 24,351 | 30,844 |
| 7 | 0 | 30,844 |

So H 0-4 read exactly the previous clock's output. H 5 mostly reads the previous one, H 6 mostly the new one, and H 7 reads the new one exactly.

For this design on this board, the output starts changing after 37.6 ns of read time and is complete by 60.2 ns. In pin time, that is 22.6 to 45.1 ns. The last wholly wrong read is H 4, and the first exact one is H 7.

At eb4ccb8 ([mithro/vgacap#95](https://github.com/mithro/vgacap/pull/95)), vgacap reads at least 80 ns after the edge by default. After these runs, #95 moved the floor to pin time: the read must see the pin at least 65 ns after the edge. The pin is sampled 2 system clocks before the read. At 133 MHz this gives the same H 10 and the same 9.5 MHz fastest clock, so batch c's max run is still the default. This floor was measured on `tt_um_vga_ca` only. `--clock-high` sets the read point per run, and [mithro/vgacap#97](https://github.com/mithro/vgacap/issues/97) asks for a value in ns.

The 40 ns default before this came from the clock-exact design note, which is not published, and not from a run. Its 25 ns basis was frame mode on `tt_um_vgacal_bars` on fpga-4, with a 25 MHz project clock at sysclk 100 MHz ([2026-11-24-frame-capture-fpga4](../2026-11-24-frame-capture-fpga4/README.md)). There, sampling at falling+0 was wrong, and falling+1 and rising+0 were exact; that page puts the change at about 25 ns. Frame mode times its sample from a different edge, so its figure is not directly comparable with these.

### c: the fastest clock, a killed host, and the bridge ([`batch-c.log`](batch-c.log), [`analyse-c.log`](analyse-c.log))

| Run | Link | Clock | Divider | H | L | Samples | Compared | Differ |
|---|---|---|---|---|---|---|---|---|
| max | serial | 9,500,000 Hz | 1 | 10 | 0 | 4,194,304 | 4,194,304 | 0 |
| killed | serial | 500,000 Hz | 14 | 8 | 7 | 2,834,432 | 2,834,432 | 0 |
| bridge | WebSocket | 500,000 Hz | 14 | 8 | 7 | 4,194,304 | 4,194,304 | 0 |

- **max:** the batch read `machine.freq()`, which gave 133,000,000. It asked for ceil(133,000,000 / 14) Hz, the fastest clock with an 80 ns read at eb4ccb8. The run took 5.08 s on the board, with `overruns=0`. Its samples are identical to batch a's.
- **killed:** the host was sent `SIGKILL` 12 s after the capture started. A held load of this bitstream took 4.86 s in [mithro/vgacap#89](https://github.com/mithro/vgacap/pull/89)'s hardware runs, so streaming had begun. After a 40 s wait the board's state equalled the state before. This run gave no `--ui-in`, and fpga-4's firmware has no manual-clock monitor, so it does not show those two being put back. When ttcap itself is killed, only the board's own clean-up runs: it releases reset and leaves the clock pin low on PIO1. The input mode and the monitor stay as the capture set them ([how-to](https://github.com/mithro/vgacap/blob/main/python/ttcap/how-to-capture-clocked.md)). The file has the opening `TIME` record and no closing one ([`analyse-c.log`](analyse-c.log) lists a single `TIME` line for it). Every sample in it is exact.
- **bridge:** the bridge was running, and the capture went through `ws://127.0.0.1:8765/serial` on the Pi. `overruns=0`, and the samples are identical to batch a's.

### kk: the design from vgacap#73 ([`batch-kk.log`](batch-kk.log), [`analyse-kk.log`](analyse-kk.log), [`kkruns.log`](kkruns.log), [`kkmodels.log`](kkmodels.log))

`tt_um_KK_VGA01` resets its game state only on a vsync edge while `rst_n` is low. Before clocked mode, its captures differed from the reference from frame 1 ([mithro/vgacap#73](https://github.com/mithro/vgacap/issues/73)).

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
- Both dumps came from the harness's mismatch investigation on 2026-11-27. Its scripts are not published.
  - **Simulator:** Verilator 5.053, from the harness's oss-cad-suite.
  - **Testbench:** the harness's [`ref_tb.cpp`](https://github.com/mithro/tt-harness-fpga-vga/blob/f7786c9/tthfv/harness/ref_tb.cpp) at f7786c9, sha256 prefix `b5f9c6c3ac25`, the same testbench the reference names.
  - **Stimulus:** `ui_in` 0 and `uio_in` 0xc0, for 6,000,000 clocks.
  - **RTL model:** the design's sources.
  - **Netlist model:** the FPGA build's own synthesised netlist (`out-default.json`), written as Verilog by Yosys 0.69+24 and simulated with the iCE40 `cells_sim.v`.
  - The tool versions were read with `--version` from the harness's oss-cad-suite when this page was written, not from a kept log of the 2026-11-27 runs. The `cells_sim.v` step is from the investigation's script.
- It is not explained. [mithro/vgacap#96](https://github.com/mithro/vgacap/issues/96) tracks it, with an unchecked hypothesis.

## Not measured

- a fractional PIO divider;
- a system clock other than 133 MHz;
- the teardown order after a stop with the clock high, on hardware;
- designs other than these two.

## Files

The `.vgacap` capture files, about 45 MB in all, are not in this repository. Without them the scripts here can't be re-run; ask on [mithro/vgacap#95](https://github.com/mithro/vgacap/pull/95) for a copy.

| File | What |
|---|---|
| [`bitstreams.log`](bitstreams.log) | bitstream sizes and sha256 |
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
| [`ttcap_main.py`](ttcap_main.py) | runs the ttcap CLI from the archived tree on the Pi |
| [`bitinfo.py`](bitinfo.py) | the bitstream sizes and hashes |

In the logs, `HOST` stands for the host's working directory, `TT` for its checkout root, and `BITSTREAMS` for its bitstream store.
