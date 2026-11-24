# Capturing Tiny Tapeout VGA with the Baochip-1x BIO: feasibility and a simulator test

Date: 2026-11-24. Design spec section 5.5 asks for "Interface stub and a
research note on the BIO simulator only". This is the note. It builds
bunnie's BIO simulator, writes capture programs equivalent to the RP2 PIO
`sample_extclk` sampler, and runs them against synthetic clock-plus-data
waveforms. No hardware was used.

Everything run for this note is beside it in `2026-11-24-bio-capture/`:
the BIO programs (`ttcap*/main.c`), the test driver (`run_capture_test.py`),
the sweep (`sweep.sh`), the table generator (`summarise.py`), a log
diagnostic (`diff_capture.py`) and the raw results (`results.jsonl`).

Conventions: every claim quotes its source (URL plus exact text). Anything
worked out rather than read is marked **INFERRED**. Anything measured in
the simulator is marked **MEASURED (sim)**. The simulator measurements come
from the real BIO RTL, but that is still not the chip.

## Summary

- **Simulator:** `baochip/bio-sim` (Apache-2.0 harness, C++ and Verilator,
  running the unmodified CERN-OHL-W-2.0 BIO RTL). It builds and runs on
  this host through its Docker image, after a one-line workaround for a
  Verilator 5.020 crash. A test bench can drive any GPIO input with a
  per-cycle waveform (`inject`), and the model is cycle-exact to the BIO RTL.
- **Capture works in simulation.** One core can wait on the project clock
  pin and read all 32 GPIOs in two instructions per sample. Every injected
  byte came back, in order, with no gaps:

  | program | max pixel clock (sim) |
  |---|---|
  | one core packing 4 samples/word | 30.4 MHz (fails at 31.8 MHz) |
  | two cores (sampler + packer), 4 x 8-bit per word | 63.6 MHz |
  | two cores, Dabao pin layout, 2 x 16-bit per word | 63.6 MHz |

  Runs of 4,800 samples at 40 MHz (two cores) and at 25 MHz (one core)
  were bit-exact. The 25-40 MHz range the project needs is covered by the
  two-core version with about 1.6x headroom. The sample point is 4-7 ns
  after the clock-pin edge, so rising-edge triggering reads the previous
  cycle's settled value, which matches what the RP2 frame modes settled on.
- **BIO clock:** documented as 700 MHz. The only 800 MHz figure found is an
  RTL code comment.
- **Not answered here:** how fast the host CPU or the BDMA can drain the
  FIFO on silicon. The simulator does not model either. That is the real
  open question for a continuous stream.
- **Hardware:** the Dabao board breaks out 22 BIO pins, but no 8
  consecutive ones. BIO16-19 plus BIO23-26 work (tested in sim with a
  16-bit sample format the vgacap header already supports). The I/O banks
  appear to run at 3.3 V on Dabao, the same as the Tiny Tapeout demo board.

## 1. Where the BIO simulators live, and building one

### 1.1 What exists

There are two. Only the first was built.

1. **`bio-sim`: the BIO block on its own.** https://github.com/baochip/bio-sim,
   cloned at `7e9c9615e1c900c7ddae1c4645a87078b217abc3` (2026-11-02).
   - GitHub description (from `gh search repos`): "Simulate BIO programs
     using the open-source RTL!"
   - README: "A Verilator harness for the `bio_bdma` block. The host CPU is
     not modelled; everything it would do (load code, poke control
     registers, start cores) is reduced to APB transactions on the block's
     slave ports, driven from C++. The original ASIC RTL is used unmodified
     and built with `+define+SIM`."
   - Licence: the repo's `LICENSE` is "Apache License Version 2.0" (GitHub
     API: `Apache-2.0`). The RTL files keep their own headers:
     `rtl/bio_bdma.sv`, `rtl/bio.sv` and `rtl/picorv32.v` carry
     "SPDX-License-Identifier: CERN-OHL-W-2.0", and `rtl/bio_bdma_wrapper.sv`
     carries "SPDX-License-Identifier: BSD-2-Clause".
   - Languages: SystemVerilog/Verilog RTL, a C++17 harness
     (`sim/sim_main.cpp`), C BIO programs built with Zig/clang
     (`sw/build.zig`), and Python helpers.
   - **The RTL matches the chip source.** `bio_bdma.sv`, `bio.sv`,
     `picorv32.v`, `regfifo.v` and `pio_divider.v` are byte-identical to
     `https://raw.githubusercontent.com/baochip/baochip-1x/main/rtl/modules/bio_bdma/rtl/`
     (checked with `diff -q` on 2026-11-24, all exit 0).
   - The Crowd Supply update named in the brief
     (https://www.crowdsupply.com/baochip/dabao/updates/dabao-boards-are-en-route-and-new-bio-tools)
     returned 403 to the fetch tool and a JavaScript challenge to curl. I
     could not read it. A search snippet of it said "bio-sim provides a C
     environment that compiles your code into assembly", which matches
     this repo. Not verified first-hand.

2. **The full-SoC Verilator flow** in https://github.com/baochip/baochip-1x
   (`verilate/`, with `bao_soc.py`, `bao_core.py`, `verilate.sh`; licence
   CERN-OHL-W-2.0), driven from xous-core's `bao1x-sim` target
   (`xtask/src/main.rs` matches `Some("bao1x-sim")`). The book says:
   - https://baochip.github.io/baochip-1x/print.html, "Simulation with
     Verilator": "Verilator does not literally run the top level RTL file
     that describes the Baochip-1x, because some portions such as the AXI
     bus fabric, analog/mixed-signal IP (PLL, USB, regulators, ADC) and
     details of the built-in self test routines are closed source. Instead,
     a version of the chip is created in Litex [...] Currently the
     best-supported and tested stub is for the BIO".
   - Same page: "Verilator is fast enough to boot the Xous OS in a
     reasonable amount of time (a couple minutes without waveform tracing;
     about 15 minutes with)."
   - Same page: "while the verilator models presented here are not
     perfectly cycle-accurate, they were accurate enough for chip
     development".

   This flow is the only one that models the host CPU (a stand-in Vexriscv
   in LiteX) and the bus that the BDMA writes to, so it is where the
   FIFO-drain question in section 3.4 would be simulated. I did not build
   it.

### 1.2 Building `bio-sim` on this host (Debian 13, x86_64)

There is no system Verilator and no podman. Docker is available. Building
the image runs `apt-get install verilator` inside an Ubuntu 24.04
container, which gives Verilator 5.020. Nothing was installed on the host.
All logs are in `/home/tim/github/TinyTapeout/tmp/bio/`.

```
cd /home/tim/github/TinyTapeout/tmp/bio
git clone https://github.com/baochip/bio-sim.git
cd bio-sim
docker build -t bio-sim .            # -> ../docker-build.log
```

**Attempt 1 failed.** The simulator binary linked, but Verilator then
aborted:

```
15.65 g++     sim_main.o verilated.o verilated_fst_c.o verilated_threads.o Vbio_bdma_wrapper__ALL.a   -lz -pthread  -pthread -lpthread -latomic   -o bio_sim
15.81 %Error: Internal Error: attempted to destroy locked Thread Pool
17.05 %Error: Verilator aborted. Suggest trying --debug --gdbbt
17.06 make: *** [Makefile:43: build] Error 255
ERROR: failed to solve: process "/bin/sh -c make build" did not complete successfully: exit code: 2
```

The Makefile passes `--build -j 0`, which uses all 88 host threads.
**INFERRED:** this is a Verilator 5.020 thread-pool bug triggered by the
high job count, not an RTL problem, because the binary had already linked.
The workaround, applied to the local clone only, was:

```
sed -i 's/--build -j 0/--build -j 8/' Makefile
docker build -t bio-sim .            # -> ../docker-build2.log, exit=0, ~60 s
```

The smoke test then passes (`../smoke.log`):

```
CONTAINER_ENGINE=docker ./container-run configs/smoke.jsonc
>> reusing image 'bio-sim'  (use --rebuild after editing rtl/ or sim/)
[cfg] fclk=700.000 MHz  pclk=fclk/16 (43.750 MHz)
[selftest] sfr_cfginfo @0x04 = 0x10000408 (expect 0x10000408) -> PASS
[done] sim_time = 902496 ps  (0 cycles)
```

There is also a prebuilt image, `ghcr.io/baochip/bio-sim:latest`. It
pulled fine, but it was created 2026-06-08, so it is older than the repo's
current harness. I did not use it.

**BIO programs** build with Zig, which is pip-installable, so `uv` handles
it without touching the system:

```
cd bio-sim/sw
uv run --no-project --with 'ziglang==0.15.2' python -m ziglang build -Dmodule=ttcap -Demit-listing=true
```

Output (`../zig-ttcap2.log`): `post-link errata: PASS (60 executable
bytes)`, `binary: ttcap/ttcap.bin (60 bytes / 15 words)`. The listing
needs a RISC-V objdump; `/usr/bin/riscv64-unknown-elf-objdump` was already
installed. The build script also checks two documented "phantom register"
errata (`sw/bio_errata_check.py`): "BUG1 phantom-rs1" for AUIPC/LUI/JAL
whose rs1 field is 16-19, and "BUG2 phantom-rs2" for an rs2 field of 20.
All programs here pass that check.

Speed: about 130-210 k fclk cycles per second without tracing (from the
harness progress bar), so one simulated millisecond at 700 MHz takes about
4 s. A whole 640x480 frame (16.7 ms) would take about a minute.

## 2. What the simulator models

- **Clocks.** `sim/sim_main.cpp` header: "Model: one fast clock `fclk`
  (fanned to aclk/hclk/dmaclk inside the wrapper) plus `pclk`, derived by
  integer division of fclk." The default is `fclk_mhz` = 700 (README: "Fast
  clock in MHz. Default `700`."). `pclk_div = (fclk_mhz >= 700.0) ? 16 : 8`.
- **GPIO inputs are driven by the test bench, one cycle at a time.**
  README: "`inject {events:[{cycle, pin, value}, …]}` - schedule
  timestamped `gpio_in` edges". The harness applies due injections before
  every fclk cycle (`void tick() { apply_due_injects(); half_step();
  half_step(); cycle++; sample_monitors(); }`). So yes, a test can feed a
  per-cycle input waveform, at fclk resolution (1.43 ns at 700 MHz). There
  is also a TCP "driven" mode for doing this from any language, which is
  "lock-step, deterministic" (README "Serve modes"). This note uses the
  batch JSONC form.
- **Accuracy.** It is the chip's BIO RTL in Verilator, so the PicoRV32
  cores, the 8-deep FIFOs, the two-flop input synchronisers and the
  quantum logic behave cycle for cycle as the RTL does. The limits are:
  - Verilator is two-state, so there is no X and no metastability. The book
    says Verilator "is incapable of representing the `X` (unknown) logic
    state" (print.html, "Simulation with Verilator").
  - Input edges land exactly on fclk edges. Analogue skew, pad delay and
    setup/hold are not modelled.
  - Every BIO-side clock domain (aclk/hclk/dmaclk) is one clock, and the
    APB side is an integer division of it. On the chip the host bus clock
    is independent (**INFERRED**).
  - The host CPU and the system bus are not modelled. The BDMA AXI master
    is tied off with `b_valid=0` (`benign_dma_inputs()`). **INFERRED:** a
    BIO store to main memory would never complete in this harness, so the
    BDMA cannot be tested with `bio-sim`.
- **FIFOs.** The FIFOs are `regfifo.v`, generated by LiteX:
  "Memory storage: 8-words x 32-bit", with a registered output stage
  (`level1 = (level0 + readable_1)`). The harness only drains them through
  APB commands that run between `run` commands. While a drain is running,
  the injection clock (`cycle`) does not advance, so the input waveform
  pauses. The cores keep running, but there are no edges to wait for.
  This is why the test below drains every 6 words.
- **Instruction timing.** The book: "on the PicoRV32, a typical instruction
  takes about three cycles to execute, as there is no pipelining"
  (https://baochip.github.io/baochip-1x/print.html, "Snapping to Quantum:
  An SPI Example", and the same sentence in
  https://www.bunniestudios.com/blog/2026/bio-the-bao-i-o-coprocessor/).
  The loop limits measured below fit this: about 3.5-3.7 aclk per
  instruction including the wake-up from a quantum stall (**INFERRED** from
  the pass/fail limits, not from a cycle trace).

## 3. The BIO programming model for capture

### 3.1 Registers used

From `sw/README.md` in bio-sim, which repeats the book's register map:

- "FIFO - 8-deep fifo head/tail access. Cores halt on overflow/underflow.
  x16 r/w fifo[0] ... x19 r/w fifo[3]"
- "Quantum - core will halt until host-configured clock divider pules
  occurs, or an external event comes in on a host-specified GPIO pin.
  x20 -/w halt to quantum"
- "x21 r/w write: (x26 & x21) -> gpio pins; read: gpio pins -> x21"
- "x25 -/w (x26 & x25) -> `1` will make corresponding gpio pin an input"

The book adds (print.html, "Design of the BIO"): "In the case of x20, the
CPU will halt until a “quantum” of time has passed (either defined by an
internal fractional clock divider, or an external clock source from a GPIO
pin)."

### 3.2 How "wait for the clock edge" works in the RTL

`rtl/bio_bdma.sv`, which is the same file as on the chip:

```
// the external clock *must* go through synchronizers to be used as an edge
extclk_selected[j] = gpio_in_sync1[extclk_gpio_aclk[j]];
...
quantum[j] <= use_extclk_aclk[j] ? (extclk_selected[j] & ~extclk_selected_q[j]) : penable[j];
```

- The host sets core *j*'s quantum source to a GPIO with `sfr_extclock`
  (0x44): `apb_cr #(.A('h44), .DW(24)) sfr_extclock (.cr({extclk_gpio_3,
  extclk_gpio_2, extclk_gpio_1, extclk_gpio_0, use_extclk}) ...`. The
  Rust API calls this `ClockMode::ExternalPin(BioPin)` with the comment
  "Use external pin as quantum source"
  (https://docs.rs/bao1x-api/0.1.0/src/bao1x_api/bio.rs.html, line 284-285).
- **Only rising edges count**: `extclk_selected & ~extclk_selected_q`. For
  falling-edge sampling, invert the clock pin with `sfr_io_i_inv` (0x6C).
  bao1x-api: "bits set to `1` in the u32 corresponding to BIO inputs that
  have the input value inverted before being passed into the register
  accessed by the core". **MEASURED (sim):** falling-edge sampling through
  `i_inv` works (tables below).
- `quantum` is a one-cycle pulse, and a core stalls only while it is in
  the x20 write: `stall[j] = (quanta_halt[j] & ~quantum[j] | ...`.
  **INFERRED:** if the code is not already waiting when an edge arrives,
  that edge is lost (there is no latch). This sets the per-sample
  instruction budget, and the "FAIL" rows below are exactly this.
- Inputs pass through two synchronising flops
  (`gpio_in_sync0 <= gpio_in; gpio_in_sync1 <= gpio_in_sync0;`). One can be
  bypassed per pin with `sfr_sync_bypass` (0x60). bao1x-api: "passed in as
  raw, unsynchronized values. This can lead to instability, but reduces
  latency."
- "Snap inputs to quantum" (`sfr_config` bit 5) latches on `penable`, the
  fractional divider, and not on the external clock (`if (penable[0])
  gpio_in_snapped <= gpio_in_cleaned;`). bao1x-api agrees: "When specified
  all GPIO inputs are aligned to the divided clock of the specified core".
  So snapping does not help an external-clock sampler. Not used here.

### 3.3 Cycle counts and maximum sample rate

**Clock: 700 MHz is the documented figure.**
- https://baochip.github.io/baochip-1x/print.html, BIO_BDMA_SFR_QDIV0:
  "fclk can be up to 700M". "ClockMode": "The clock for the BIO is `FCLK`."
  "Electrical Characteristics": "Normal Operation | T=25°C | | 90 | | mA |
  Clock=700 MHz".
- https://www.bunniestudios.com/blog/2026/bio-the-bao-i-o-coprocessor/:
  "the Baochip-1x’s implementation running at 700MHz".
- The only 800 MHz is an RTL comment in `bio_bdma.sv` line 877: "the
  penalty is small (aclk ~ 800MHz => 1.25ns delay ...". **INFERRED:** that
  was a design-time target. Use 700 MHz. The runtime value is read with
  `get_fclk()` ("The current `FCLK` value can be read through the
  `ClockManager` API, using the `get_fclk()` call"). I could not check what
  a Dabao actually runs at.

**MEASURED (sim)**, fclk = 700 MHz. The project clock period (in aclk
cycles) was swept with random data (seed 1) changing 2 aclk after each
rising edge. 480 project clocks per run. Pass means every captured byte
equals the injected byte for its own edge, from edge 0, with no gap or
repeat.

| period (aclk) | pixel clock at 700 MHz | single rise | single fall | dual rise | dual fall | dual16 rise | dual16 fall |
|---|---|---|---|---|---|---|---|
| 40 | 17.5 MHz | pass | pass | pass | pass | pass | pass |
| 28 | 25.0 MHz | pass | pass | pass | pass | pass | pass |
| 24 | 29.2 MHz | pass | pass | pass | pass | pass | pass |
| 23 | 30.4 MHz | pass | pass | pass | pass | pass | pass |
| 22 | 31.8 MHz | FAIL | pass | pass | pass | pass | pass |
| 21 | 33.3 MHz | FAIL | FAIL | pass | pass | pass | pass |
| 20 | 35.0 MHz | FAIL | FAIL | pass | pass | pass | pass |
| 18 | 38.9 MHz | FAIL | FAIL | pass | pass | pass | pass |
| 17.5 | 40.0 MHz | FAIL | FAIL | pass | pass | pass | pass |
| 16 | 43.8 MHz | FAIL | FAIL | pass | pass | pass | pass |
| 14 | 50.0 MHz | FAIL | FAIL | pass | pass | pass | pass |
| 13 | 53.8 MHz | FAIL | FAIL | pass | pass | pass | pass |
| 12 | 58.3 MHz | FAIL | FAIL | pass | pass | pass | pass |
| 11 | 63.6 MHz | FAIL | FAIL | pass | pass | pass | pass |
| 10.5 | 66.7 MHz | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| 10 | 70.0 MHz | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| 9 | 77.8 MHz | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |
| 8 | 87.5 MHz | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL |

What the modes are:
- `single`: `ttcap` on core 0. Wait, read, mask, shift, OR, four times,
  then push. Its longest gap between two waits is after sample 3:
  `mv a1,x21; slli; or; mv x16,a0; j; li x20,0`, which is 6 instructions.
  It needs about 22-23 aclk, so it stops at about 30 MHz.
- `dual`: `ttcap_raw` on core 0 does `mv x20,zero; mv x16,x21` per sample
  (unrolled by 4). `ttcap_pack` on core 1 is free-running (divider 1). It
  pops four raw words from FIFO0, keeps bits 7:0, packs them and pushes
  to FIFO1. The sampler's longest gap is 3 instructions, and the limit is
  11 aclk (63.6 MHz). The packer keeps up because 13 instructions per 4
  samples is about 12 aclk per sample, and FIFO0 absorbs the jitter.
- `dual16`: the same sampler with `ttcap_pack16`. It keeps BIO16-31 and
  packs 2 x 16-bit samples per word, for the Dabao pin layout
  (section 5.2).

**Answer to "max sample rate":** about 30 MHz with one core packing bytes,
and about 63 MHz with a sampler core plus a packer core, at 700 MHz.
**INFERRED** from the limits: the two-core sampler needs about 11 aclk
per sample, so its maximum pixel clock is about fclk/11. The single-core
version needs about 23 aclk, so about fclk/23. A 25.175 MHz 640x480 pixel
clock therefore needs a BIO clock of at least about 280 MHz with two cores,
or about 580 MHz with one. 40 MHz (800x600@60) needs the two-core version.

Long runs, all pass, all from edge 0, no gaps:

| run | samples | result |
|---|---|---|
| `dual`, falling edge, 40 MHz | 4,800 | bit-exact |
| `dual16`, Dabao layout, falling edge, 40 MHz | 4,800 | bit-exact |
| `single`, falling edge, 25 MHz | 4,800 | bit-exact |

**Where in the cycle the BIO samples.** **MEASURED (sim)** at 25 MHz
(period 28) with rising-edge triggering, sweeping `tco` (how long after
the clock-pin edge the data pins change). "new" means the sample is the
value driven after this edge. "prev" means it is the value before it.
"mixed" means it depends on the sample slot within the unrolled loop.

| tco (aclk after clock-pin edge) | single-rise | single-rise-sb | dual-rise |
|---|---|---|---|
| 0 | new | new | new |
| 1 | new | new | new |
| 2 | new | new | new |
| 3 | new | new | prev |
| 4 | mixed | new | prev |
| 5 | prev | mixed | prev |
| 6 and up (6-16 tested) | prev | prev | prev |

`sb` means the data pins use `sync_bypass`. So the BIO samples the data
pins about 3-5 aclk (4-7 ns at 700 MHz) after the clock edge reaches the
pin. The exact cycle moves by about one with code alignment and slot.
`sync_bypass` on the data pins moves the sample point about one cycle
*later*. Nothing moves it earlier than about 3 cycles.

For Tiny Tapeout, compare this with the project's own hardware finding.
On the FPGA emulation board, `uo_out` "changes about 2-3 of them (~25 ns,
FPGA + pads + synchroniser) after each rising edge", and the frame modes
"now default to rising+0" (`docs/results/2026-11-24-frame-capture-fpga4/README.md`).

- **INFERRED:** rising-edge triggering on the BIO samples 4-7 ns after the
  edge. That gives the previous cycle's value ("prev" above), which is
  correct as long as `uo_out` changes more than about 6 aclk (8.6 ns) after
  the edge at the BIO pin. The ~25 ns RP2 measurement suggests it does, but
  that figure includes the RP2's own synchroniser, and the TT ASIC's
  clock-to-out on this wiring is unmeasured.
- **INFERRED:** falling-edge triggering (clock pin inverted with `i_inv`)
  samples half a period plus 4-7 ns after the rising edge. That is 24-27 ns
  at 25 MHz, which is right in the ~25 ns window where the FPGA board's
  outputs were found to change. It would fail the same way the RP2
  falling-edge sampler did.
- Recommendation: keep the edge selectable, as the PIO programs do (it
  costs only the `i_inv` bit), default to rising, and settle it with the
  same edge/delay sweep `sweep-bars-25mhz.log` used, once there is
  hardware.

### 3.4 Draining the FIFO: host and DMA

- **Data rate needed** (**INFERRED**, arithmetic): 4 samples per word means
  pixclk/4 words per second. That is 6.3 M words/s (25 MB/s) at 25.175 MHz,
  and 10 M words/s (40 MB/s) at 40 MHz. The Dabao 16-bit layout doubles
  that.
- **Host CPU path.** The host reads `SFR_RXFn`: "Reads remove an entry from
  FIFO0 or returns the last value if empty" (print.html,
  BIO_BDMA_SFR_RXF0). There are also per-FIFO "page aliases" (print.html,
  "Concept: Page-Aliased Register Access"). The CPU is a "350MHz Vexriscv
  RV32-IMAC" (print.html, Introduction). **Not verified:** how many CPU
  cycles one RXF read costs across the APB/CDC. If it were around 10, the
  CPU would spend about 60-100% of its time draining at 25-40 MHz, which is
  not workable for a continuous stream (**INFERRED**). Whole-frame capture
  can use a burst instead: let the BIO fill a buffer while the CPU only
  drains.
- **BDMA path (preferred, INFERRED).** The book: "The BIO is also capable
  of doing DMA via the “BDMA” extension. This extension allows the
  load/store units of the PicoRV32 cores access the SoC’s bus, with a
  “dumb” priority resolver in case of contending accesses (lowest numbered
  core always wins; other cores halt). [...] It’s not as fast as the
  fastest DMA engines" and "access to main memory is blocked by a
  whitelist, which by default is empty" (print.html, "Design of the BIO").
  The book's own example is a core doing `lw a0, 0(x16)` / `sw a0, 0(x17)`
  with another core generating addresses. For capture, a third core would
  `mv a0, x17; sw a0, 0(a1); addi a1, a1, 4` into a whitelisted SRAM ring
  (`setup_dma_windows`: "Allows BIO cores to DMA to/from the windows
  specified in `windows`. DMA filtering is on by default with no windows
  allowed."). Store throughput on silicon is unknown, and `bio-sim` cannot
  measure it (section 2). The full-SoC Verilator flow could.
- **System DMA.** The `DMAREQ_MAP` registers go the other way:
  "configure the mapping of system interrupts onto the event register
  inside the BIO" (print.html, BIO_BDMA_SFR_DMAREQ_MAP_CR_EVMAP0). I found
  no documented path for the system DMA to be paced by BIO FIFO levels.
  Not verified either way.

## 4. The capture programs

Single core (`2026-11-24-bio-capture/ttcap/main.c`). The host sets
`clock core 0 external pin 8` and, for falling-edge sampling,
`i_inv = 1<<8`:

```c
set_gpio_mask(0x1FF);
set_input_pins(0x1FF);
__asm__ volatile (
    "ttcap_loop:\n"
    "mv   x20, zero\n"  "mv a0, x21\n"  "andi a0, a0, 255\n"
    "mv   x20, zero\n"  "mv a1, x21\n"  "andi a1, a1, 255\n" "slli a1, a1, 8\n"  "or a0, a0, a1\n"
    "mv   x20, zero\n"  "mv a1, x21\n"  "andi a1, a1, 255\n" "slli a1, a1, 16\n" "or a0, a0, a1\n"
    "mv   x20, zero\n"  "mv a1, x21\n"                       "slli a1, a1, 24\n" "or a0, a0, a1\n"
    "mv   x16, a0\n"
    "j    ttcap_loop\n" ::: "a0", "a1", "memory");
```

The first sample goes in bits 7:0, so the vgacap `VGCH` flags have bit0 =
0, `sample_bits` = 8 and `samples_per_word` = 4. This is the PIO
`sample_extclk` equivalent, but it only reaches about 30 MHz.

Two cores (recommended): `ttcap_raw` on core 0 (external clock) runs

```
ttcap_raw_loop: mv x20,zero; mv x16,x21; (x4) ; j ttcap_raw_loop
```

and `ttcap_pack` on core 1 (divider 1, never waits on a quantum) pops four
raw words from x16, packs them as above, and writes them to x17
(FIFO1, which the host or a BDMA core reads). `ttcap_pack16` is the Dabao
variant. It pops one raw word and shifts it right by 16, pops a second and
ANDs it with 0xFFFF0000, ORs the two and pushes the result. That gives
2 x 16-bit samples per word (`sample_bits` = 16, `samples_per_word` = 2),
6 instructions per 2 samples.

### 4.1 The test

`run_capture_test.py` writes a JSONC command list for `bio-sim`:
- load the program(s);
- `clock` core 0 `external` on the clock pin;
- optionally `io_config` `i_inv` / `sync_bypass`;
- `start`, then a lead-in `run`;
- one `inject` with every clock and data edge;
- alternating `run` (6 output words' worth of project clocks) and
  `fifo_drain`.

It runs the image with `docker run --rm -v <bio-sim>:/work --user uid:gid
bio-sim configs/<name>.jsonc`, parses the `[fifo_drain]` lines, unpacks
the words using the layout's pin list, and requires the bytes to equal
the injected `data[0:]` ("new") or the same delayed by one edge ("prev").

Example: the first drain of the 25 MHz single-core run
(`runs/ttcap-single-rise-p28-tco2.log`):

```
[load] sw/ttcap/ttcap.bin -> core 0 (15 words)
[clock] core 0 <= external pin 8  (extclock=0x000081)
[start] sfr_ctrl @0x00 <= 0x111 (en=0x1 restart=0x1 clkdiv=0x1)
[inject] scheduled 2400 event(s)
[fifo_drain] bank 0 level=6, reading 6
[fifo_drain]   [0] = 0x3c822044  (s16=8260)
[fifo_drain]   [1] = 0xc2f1e6fd  (s16=-6403)
```

`0x3c822044` holds samples `44 20 82 3c`, the first four injected bytes
of seed 1 (`random.Random(1)`: 0x44, 0x20, 0x82, 0x3c, ...).

**A harness pitfall found on the way.** At first, runs longer than a few
hundred samples failed with exactly four samples missing at one point.
The cause was in the test bench, not the BIO. The harness draws an
unbuffered progress bar on stderr. With stdout and stderr merged into one
log, it landed in the middle of buffered `[fifo_drain]` lines, for example
`[fifo_drain]   [3] = 0x7[run] [#####...`, so whole words failed to parse.
`run_capture_test.py` now writes the two streams to separate files. After
that change every run is deterministic, and `sweep.sh` gives identical
tables on a second run (`diff` exit 0).

Reproduce:

```
D=docs/research/2026-11-24-bio-capture
for m in ttcap ttcap_raw ttcap_pack ttcap_pack16; do
  mkdir -p <bio-sim>/sw/$m && cp $D/$m/main.c <bio-sim>/sw/$m/
  (cd <bio-sim>/sw && uv run --no-project --with 'ziglang==0.15.2' python -m ziglang build -Dmodule=$m)
done
$D/sweep.sh <bio-sim> <logdir>      # 150 runs, ~2.5 min with 70 in parallel on 88 threads
```

## 5. Integrating with vgacap and wiring a Tiny Tapeout board

### 5.1 Software architecture (INFERRED, design proposal)

The vgacap side needs nothing new. `RAW ` and `FRAM` already carry "the
32-bit words the PIO's autopush/DMA produced, with the header saying how
many samples a word holds and whether the first sample sits in the low or
the high bits" (`2026-09-15-stream-format.md`). The BIO words fit as they
are: 8/4 for the byte layout, and 16/2 with a `signal_map` for Dabao.

On the Baochip side, the RP2 structure carries over:

| RP2 piece | Baochip equivalent |
|---|---|
| PIO SM `wait 0/1 pin clk; in pins, N` | BIO core 0 `ttcap_raw` (external quantum) |
| PIO autopush to RX FIFO | BIO core 1 packer writes to FIFO1 |
| DMA into SRAM ring / frame buffer | BIO core 2 BDMA stores into a whitelisted SRAM window, or the Vexriscv reading `RXF1` |
| `sample_frame` (vsync/hsync gating) | another loop on core 0, or core 3 watching vsync and gating core 0 through an event bit (x28/x30) |
| USB CDC + command protocol + vgacap chunks | Baochip USB: "USB 2.0 Device-mode, Supports High Speed and Full Speed" (print.html, "USB Main Features") |

A `vgacap_backend` for it would be a host-side serial transport, like
RP2's, talking to Baochip firmware (Xous app or bare-metal
[dabao-sdk](https://github.com/ArmstrongSubero/dabao-sdk), which print.html
calls "a C SDK for Baochip-1x [...] for bare-metal development on the Dabao
evaluation board"). USB High Speed (480 Mbit/s) is far faster than the
~700 KB/s measured on the RP2350's Full Speed CDC
(`2026-11-24-board-rle-throughput.md`). **INFERRED:** continuous 8-bit
streaming at 25 MHz (25 MB/s) is plausible over HS bulk, which tops out at
around 40 MB/s in practice. 40 MHz (40 MB/s) and the 16-bit Dabao layout
(50-80 MB/s) are not, so they need whole-frame capture into the 2 MiB SRAM
(print.html: "2MiB of integrated SRAM"). A 800x525 frame is 420 KB at
8 bits or 840 KB at 16 bits, so it fits.

### 5.2 Wiring a Tiny Tapeout board to a Dabao

- **BIO pins on Dabao** (https://github.com/baochip/dabao
  `docs/pinout/pins.csv`, commit `fa4b278`): BIO1-5 (PB1-PB5), BIO11-14
  (PB11-PB14), BIO16-19 (PC0-PC3), BIO23-29 (PC7-PC13). BIO0 and BIO6-10
  are not broken out, and neither are BIO20-22 or BIO30-31. So **there is
  no run of 8 consecutive BIO pins**. The longest is BIO23-29, which is 7.
- **The BIO owns these pins when active.** The datasheet table for every
  PB/PC pin says "BIO, when active, overrides all GPIO/AF settings", and
  "BIO pin 0 is PortB pin 0, BIO pin 18 is PortC pin 2, etc." (print.html,
  "I/O List" and "A Simple API Example").
- **Avoid PC13 (BIO29).** On the Dabao schematic (`dabao_v3c.pdf`) it goes
  to SW2, "press to toggle bootloader mode (also disconnects USB)", and to
  the USB switch `SEL` (read from the schematic image).
- **Tested layout (MEASURED (sim), `dual16`):** uo_out[3:0] on BIO16-19
  (Dabao pins 14, 12, 11, 10 = PC0-PC3), uo_out[7:4] on BIO23-26 (pins 9,
  7, 6, 5 = PC7-PC10), and the project clock on BIO27 (pin 4, PC11). In
  16-bit sample coordinates (BIO16 = bit 0), uo_out[7:0] sit at bits
  0,1,2,3,7,8,9,10. With the Tiny VGA Pmod map `(7, 3, 0, 4, 1, 5, 2, 6)`
  (hsync=uo7, vsync=uo3, r1=uo0, ...), the vgacap `signal_map` would be
  `(10, 3, 0, 7, 1, 8, 2, 9)` (**INFERRED**, mechanical translation, not
  run through the decoder).
- A board that breaks out every pin, such as `baochip/longbao` ("Baochip-1x
  Development Board that Breaks out All the Pins", GitHub description),
  would allow BIO0-7 plus a clock pin and the plain 8-bit layout. I did not
  check its pinout.
- **Voltage.** Banks B and C are 1.8-3.3 V capable: "**VDD33_BCPAD** = 1.8V
  to 3.3V: I/O supplies for banks B and C. Provided through `VDDIO` balls."
  (print.html, "Power Supply Schemes"). On Dabao the `VDDIO` balls appear
  to be tied to the board's +3.3 V rail (read from the schematic image,
  not from a netlist: **INFERRED**, check before wiring). Tiny Tapeout: "The
  demo board provides 3.3V IO supply voltage." and "The input pins are not
  5V tolerant." (https://tinytapeout.com/specs/gpio). Both sides at 3.3 V
  means a direct connection with a common ground should work. Add series
  resistors (about 33-100 ohm) at the source to tame ringing on flying
  leads (**INFERRED**, general practice).
- **Output speed on the TT side.** https://tinytapeout.com/specs/gpio:
  "Maximum output frequency | 33 MHz" and "For SKY130 the official rating
  is 33 MHz". That limits the TT chip, not the BIO, but it is why 25 MHz
  designs are the safe target.
- **Clock source (INFERRED, open).** On the RP2 the microcontroller *is*
  the project clock source and samples its own pin. With a Baochip
  alongside the demo board, either the Baochip taps the clock wire that
  the RP2 drives into the TT chip (and waits on it on BIO27, as tested), or
  a BIO core generates the project clock itself (a "selfclk" mode, with the
  fractional divider's jitter caveat in bao1x-api: "Fractional component
  means the “average” frequency is achieved by occasionally skipping
  clocks. This means there is jitter in the edge timing."). I have not
  checked where the demo board exposes the clock net.

## What I could not verify

1. Anything on silicon or a Dabao board. All numbers are from `bio-sim`.
2. The Crowd Supply "new BIO tools" update (403 and JavaScript challenge).
3. The FIFO drain rate of the Vexriscv through `RXFn`, and the BDMA store
   throughput. Neither is modelled in `bio-sim`, and I did not build the
   full-SoC Verilator / xous `bao1x-sim` flow.
4. The `fclk` a Dabao actually runs the BIO at under Xous or dabao-sdk
   (documented maximum 700 MHz).
5. Real pad timing: synchroniser behaviour under metastability, input
   delay, TT clock-to-output and skew. The sim's sample point
   (3-5 aclk after the clock edge) assumes ideal pins.
6. Exact cycles per instruction from a waveform trace. The ~3.5-3.7
   cycles per instruction figure is inferred from pass/fail limits.
7. Dabao `VDDIO` = 3.3 V was read from the schematic drawing, not from a
   netlist or a measurement.
8. Whether the 800 MHz RTL comment reflects any shipping clock option.
