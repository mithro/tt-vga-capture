# Milestone 3: first real picture via a MicroPython PIO prototype — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture a real Tiny Tapeout VGA project at Welland with a PIO program loaded into the stock MicroPython firmware, stream the samples to the Pi, and produce the first committed PNG through `vgacap-frames`.

**Architecture:** A host-side Python package `ttcap` talks raw-REPL to the board over the serial device on the Pi (or the WebSocket bridge for debugging). It pushes a MicroPython capture script that assembles the sampler PIO program with `rp2.asm_pio`, drains the RX FIFO with two chained `rp2.DMA` channels into alternating buffers, and writes `vgacap` stream chunks to USB CDC. The host receives, validates and stores the stream; `vgacap-frames` (Milestone 2) renders PPM/PNG. Slow project clock first (whatever the measured USB throughput supports), then higher clocks with dropped-sample accounting.

**Tech Stack:** Python 3.11 with `uv` (pyserial, websockets, Pillow), MicroPython 1.24 (RP2040 boards) / 1.29-preview (RP2350 boards), `rp2.PIO`, `rp2.DMA`, the `vgacap` C tools from Milestone 2.

**Spec:** `docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md` §5.3 (capture modes, PIO programs), §5.7 (tools), §7 (error handling), §8 (testing). Facts: `docs/research/2026-09-15-welland-boards-and-gpio.md`, `docs/research/2026-09-15-board-firmware-probe.md`.

## Global Constraints

- Apache-2.0; SPDX headers on every file.
- Python via `uv` only; the `ttcap` package lives in `vgacap/python/ttcap/` and its tests in `vgacap/python/tests/`.
- Never blame the hardware: any wrong picture is a code bug until measured otherwise; measurements go to `tt-vga-capture/docs/research/`, pictures to `docs/results/`.
- The WebSocket bridge (`ws://<pi>:8765/serial`) is for debugging and tests only. Performance captures run on the Pi, own `/dev/ttboard` directly, and stop/start `fpgas-tt` around the capture (`sudo systemctl stop fpgas-tt` / `start`), always restoring it.
- One board at a time; leave the board with the project disabled and the daemon running.
- Board facts (verified 2026-09-15): tt07 RP2040, clk GPIO0, uo_out GPIO 5,6,7,8,13,14,15,16, MicroPython 1.24, ~85 KB free heap, 133 MHz. fpga-1 RP2350, clk GPIO16, uo_out GPIO33..40, `PIO.gpio_base(16)` required, ~417 KB free heap, 133 MHz.
- Stream layout for RP2040 boards: `sample_bits=12`, `samples_per_word=2`, `flags=1` (FIRST_SAMPLE_MSB: the PIO uses `in_shiftdir=SHIFT_LEFT`, so after two `in pins, 12` the ISR holds sample0 in bits 23:12 and sample1 in bits 11:0 and autopush at 24 pushes bits 23:0), `signal_map=(11,3,0,8,1,9,2,10)`. For RP2350 boards: `sample_bits=8`, `samples_per_word=4`, `flags=1` (SHIFT_LEFT, sample0 in bits 31:24), Tiny VGA map `(7,3,0,4,1,5,2,6)`. **Superseded assumption (2026-09-15 review):** the original plan said SHIFT_RIGHT with flags=0; with shift-right the 24 valid bits land in ISR bits 31:8, which the format cannot describe without an extra shift.
- The MicroPython raw REPL ends a script's stdout with an unescaped 0x04 that binary sample data can also contain, so the host must read the board's output **length-driven**: parse each chunk's tag and u32 length and read exactly that many payload bytes; an 8-byte header that starts with 0x04 marks the end of script output (stderr and the `>` prompt follow). `RawRepl.exec_stream` is for text-only output.

## File structure

```
vgacap/python/ttcap/__init__.py
vgacap/python/ttcap/repl.py            raw-REPL transport: SerialLink, WebSocketLink, exec(), upload()
vgacap/python/ttcap/boards.py          board profiles: pin numbers, sample layout, PIO gpio_base, per-slug lookup
vgacap/python/ttcap/mp/capture_rp2.py  MicroPython script pushed to the board (PIO + DMA + chunk writer)
vgacap/python/ttcap/mp/throughput.py   MicroPython script: blast N bytes to USB CDC
vgacap/python/ttcap/capture.py         host side: select project, set clock, run capture, write .vgacap
vgacap/python/ttcap/cli.py             `ttcap` entry points: probe, throughput, capture, png
vgacap/python/tests/test_ttcap_boards.py
vgacap/python/tests/test_ttcap_repl.py    (against a fake raw REPL on a pty)
vgacap/python/tests/test_capture_rp2_pio.py (assembles the PIO program with a host-side pioasm check)
tt-vga-capture/docs/research/2026-09-XX-usb-cdc-throughput.md
tt-vga-capture/docs/results/2026-09-XX-first-capture-<shuttle>-<project>/
```

---

### Task 1: Board profiles and the raw-REPL link

**Files:**
- Create: `python/ttcap/__init__.py`, `python/ttcap/boards.py`, `python/ttcap/repl.py`, `python/tests/test_ttcap_boards.py`, `python/tests/test_ttcap_repl.py`
- Modify: `pyproject.toml` (add `pyserial>=3.5`, `websockets>=12`; package `ttcap`; script `ttcap = "ttcap.cli:main"`)

**Interfaces:**

```python
# boards.py
@dataclass(frozen=True)
class BoardProfile:
    name: str                 # "rp2040-tt06map" | "rp2350-dbv3"
    clk_gpio: int
    uo_gpios: tuple[int, ...] # 8 entries, uo_out[0..7]
    pio_gpio_base: int        # 0 or 16
    in_base: int              # PIO in_base GPIO for the sampler
    in_count: int             # bits per `in pins`
    sample_bits: int; samples_per_word: int; flags: int
    signal_map: tuple[int, ...]
RP2040_TT06 = BoardProfile("rp2040-tt06map", 0, (5,6,7,8,13,14,15,16), 0, 5, 12, 12, 2, 0, (11,3,0,8,1,9,2,10))
RP2350_DBV3 = BoardProfile("rp2350-dbv3", 16, tuple(range(33,41)), 16, 33, 8, 8, 4, 0, (7,3,0,4,1,5,2,6))
def profile_from_gpio_map(m: dict[str, int]) -> BoardProfile   # from GPIOMap.all() output; raises ValueError if neither layout
WELLAND = {"tt03p5": ..., "tt04": ("pi-sw2-p4", RP2040_TT06), ..., "fpga-1": ("pi-sw2-p33", RP2350_DBV3), ...}

# repl.py
class ReplLink(Protocol):
    def write(self, data: bytes) -> None
    def read(self, timeout: float) -> bytes         # whatever is available, b"" on timeout
    def close(self) -> None
class SerialLink(ReplLink):   # pyserial, 115200, exclusive=True
class WebSocketLink(ReplLink) # websockets sync client
class RawRepl:
    def __init__(self, link: ReplLink) -> None
    def enter(self) -> None                   # Ctrl-C x2, Ctrl-A, wait for "raw REPL; CTRL-B to exit"
    def exit(self) -> None                    # Ctrl-B
    def exec(self, code: str, timeout=10.0) -> tuple[str, str]  # (stdout, stderr) using Ctrl-D framing "OK<out>\x04<err>\x04>"
    def exec_stream(self, code: str) -> Iterator[bytes]        # yields raw bytes after "OK" until "\x04" — for capture streams
    def upload(self, name: str, source: str) -> None            # writes a file on the board in base64 chunks (256 bytes)
```

- [ ] **Step 1: Write failing tests**

`test_ttcap_boards.py`: `profile_from_gpio_map` returns `RP2040_TT06` for the tt07 map dict quoted in the firmware probe note and `RP2350_DBV3` for the fpga-1 map; raises for `{}`; `WELLAND["tt07"] == ("pi-sw2-p7", RP2040_TT06)`.

`test_ttcap_repl.py`: a fake raw REPL served on a `pty` (`os.openpty`) in a thread: on `\x01` replies `raw REPL; CTRL-B to exit\r\n>`; on `<code>\x04` replies `OK` + `eval(code)` printed + `\x04\x04>`; test `RawRepl(SerialLink(slave_name)).exec("print(1+1)") == ("2\r\n", "")`, and `exec_stream("...")` yields the bytes between OK and `\x04`.

- [ ] **Step 2: Run to verify failure** (`uv run pytest -q python/tests/test_ttcap_*`)
- [ ] **Step 3: Implement** (`repl.py` ~120 lines: the framing is MicroPython's documented raw-REPL protocol; `upload` uses `f=open(name,'wb')` then `f.write(ubinascii.a2b_base64(b'...'))` chunks, then `f.close()`).
- [ ] **Step 4: Run tests, pass**
- [ ] **Step 5: Commit** (`ttcap: board profiles and raw-REPL link`)

---

### Task 2: USB CDC throughput measurement (research)

**Files:**
- Create: `python/ttcap/mp/throughput.py`, `python/ttcap/cli.py` (subcommand `throughput`), `tt-vga-capture/docs/research/2026-09-XX-usb-cdc-throughput.md`

MicroPython script (uploaded and run via `exec_stream`): `import sys; b = bytearray(range(256)) * 128; n = <total>//len(b); for i in range(n): sys.stdout.buffer.write(b)`. The host counts bytes and time; verifies the byte pattern for corruption. Run three ways: (a) on the Pi with `SerialLink('/dev/ttboard')` while `fpgas-tt` is stopped; (b) on the Pi through `WebSocketLink('ws://127.0.0.1:8765/serial')`; (c) from the dev machine through the SSH tunnel. Sizes 1 MB and 8 MB. Both tt07 (RP2040) and fpga-1 (RP2350).

- [ ] **Step 1: Implement the script and the `ttcap throughput --link serial:/dev/ttboard --bytes 8000000` command**
- [ ] **Step 2: Run on pi-sw2-p7 and pi-sw2-p33** (copy the `vgacap` checkout to the Pi under `~/vgacap`, `uv run ttcap ...`; stop and restart `fpgas-tt` around the serial runs)
- [ ] **Step 3: Write the research note** with a table (board, link, bytes, seconds, KB/s, corruption yes/no) and the derived maximum project clock for each sample layout: `clock_max = KB/s * 1024 / bytes_per_sample`.
- [ ] **Step 4: Commit both repos**

---

### Task 3: The MicroPython capture script (`capture_rp2.py`)

**Files:**
- Create: `python/ttcap/mp/capture_rp2.py`, `python/tests/test_capture_rp2_pio.py`

The script is parameterised by a dict literal the host prepends (`CFG = {...}`): `clk_gpio`, `in_base`, `in_count`, `gpio_base`, `push_thresh` (24 for 12-bit x2, 32 for 8-bit x4), `buf_words` (e.g. 4096), `max_bytes` (0 = until stopped), `edge` ("falling" default: `wait(1, pin, 0); wait(0, pin, 0); in_(pins, in_count)`; "rising": the other order).

PIO program (external clock; `wait(1, gpio, n)` takes the GPIO index relative to the PIO's GPIOBASE, so n = clk_gpio - gpio_base; `in_(pins, n)` with `in_base` at the first uo_out pin). The `rp2.asm_pio` decorator clears the function's globals while assembling, so CFG-derived values must be closure variables of a factory function, not module globals:

```python
@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_LEFT, autopush=True, push_thresh=PUSH, fifo_join=rp2.PIO.JOIN_RX)
def sampler():
    wrap_target()
    wait(1, gpio, CLK)
    wait(0, gpio, CLK)     # falling edge: outputs settled
    in_(pins, IN_COUNT)
    wrap()
```

`in_(pins, 12)` with `SHIFT_LEFT` and `push_thresh=24`: after two samples the ISR holds sample0 in bits 23:12 and sample1 in bits 11:0; autopush pushes the ISR. That is `samples_per_word=2`, `flags=1` (FIRST_SAMPLE_MSB), exactly the header the host writes. Input pads (clock and the `in_count` pins) must be configured as inputs with `machine.Pin(n, machine.Pin.IN)` before the state machine starts (RP2350 pads reset isolated). The DMA re-arm happens inside each channel's IRQ handler (chaining does not reload WRITE_ADDR/TRANS_COUNT); an overrun is a full flag that is still set when the handler fires again, reported in a `TIME` chunk, never silent.

DMA: two `rp2.DMA()` channels, each `config(read=PIO RX FIFO address, write=buf_i, count=buf_words, ctrl=pack_ctrl(size=2, inc_read=False, inc_write=True, treq_sel=DREQ, chain_to=other, irq_quiet=False))`, started on channel 0; `irq(handler)` sets a flag for "buffer i full"; main loop waits for the flag, writes `RAW ` chunk header (`b"RAW " + u32 len + u32 sample_count`) then `buf_i` to `sys.stdout.buffer`, and counts overruns (flag already set for the buffer being written = overrun; emit a `TIME` chunk with `dropped_samples`). The RX FIFO register address: `0x50200000 + 0x20 + 4*sm` for PIO0 on RP2040 (`PIO0_BASE + RXF0`), RP2350 PIO0_BASE `0x50200000` too; DREQ = `pio_num*8 + sm + 4` (RX DREQs are TX+4: `DREQ_PIO0_RX0 = 4`). The host verifies these constants against the datasheets and quotes the table in the code comment.

Host-side test: assemble the program with a small pure-Python PIO encoder check (the `rp2` module is not available on the host): the test only checks the script's text contains the expected instruction sequence and that `CFG` substitution produces valid Python (`compile()`), plus the DREQ/address arithmetic helper `rxf_addr(pio, sm)` and `rx_dreq(pio, sm)` which the script and the host both import from `boards.py`.

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Implement the script**
- [ ] **Step 3: Bench test on fpga-1 with a demo bitstream that has VGA output** (from `GET /designs`; if none, the `tt_um_vga_pattern` demo is planned by fpgas.online, else wait for Milestone 4) and on tt07 with `tt_um_rejunity_vga` (VGA Checkers) at `clock_hz = 100_000`: run for 10 s, confirm chunks arrive with no overruns.
- [ ] **Step 4: Commit**

---

### Task 4: Host capture flow and `ttcap capture`

**Files:**
- Create: `python/ttcap/capture.py`, extend `python/ttcap/cli.py`

Flow: `RawRepl.enter()`; `exec("tt.shuttle[<macro>].enable()")` (or `tt.shuttle.tt_um_x.enable()` per SDK 2.x/3.x, both supported); `exec("tt.clock_project_PWM(<hz>)")`; `exec("tt.reset_project(True); tt.reset_project(False)")` ... then upload and run `capture_rp2.py` via `exec_stream`, prepend the `VGCH` header written by the host with `vgacap.stream.Writer` (desc = `"<slug> <macro> clock=<hz> mode=extclk edge=falling"`), append the board's chunks verbatim, stop after `--seconds` or `--frames`-worth of bytes by sending Ctrl-C, `exec("tt.clock_project_stop()")`, `exit()`. Output `<out>.vgacap`, then run `build/vgacap-frames` and convert PPMs to PNG with Pillow (`ttcap png`).

- [ ] **Step 1: Implement**
- [ ] **Step 2: First capture: tt07 VGA Checkers** at 100 kHz, 3 frames, on pi-sw2-p7 with the daemon stopped. Then tt08 VGA Tiny Logo, tt08 Glyph Mode.
- [ ] **Step 3: Commit results** to `tt-vga-capture/docs/results/2026-09-XX-first-capture-tt07-tt_um_rejunity_vga/` (PNG, `vgacap-frames` output, the exact commands, the stream file if < 2 MB else a note where it is).
- [ ] **Step 4: Commit**

---

### Task 5: Clock sweep and dropped-sample accounting (research)

Run the capture at 100 kHz, 250 kHz, 500 kHz, 1 MHz, 2 MHz on tt07 and fpga-1; record overruns per frame and whether the picture stays pixel-identical (`vgacap-diff` is Milestone 5; use `numpy` array equality on the PNGs for now). Write `docs/research/2026-09-XX-rp2-micropython-capture-rate.md`. This sets the slow-clock default and motivates Milestone 6 (whole-frame capture) and 8 (compression).

---

## Self-review

- Spec §5.3 slow-clock streaming: Tasks 3-4. External-clock sampler with the falling-edge decision recorded: Task 3. Error handling rows "FIFO overrun" (TIME chunk with dropped count) and "serial busy" (stop the daemon): Tasks 3-4. §8 capture-rp2 HIL: Tasks 3-5. Self-clocked, whole-frame, windowed modes: later milestones by design.
- Open decision to make during Task 3, ledgered when made: whether MicroPython can keep up writing 16 KB buffers to USB while DMA fills the other; if not, reduce `buf_words` or the project clock, never guess.
