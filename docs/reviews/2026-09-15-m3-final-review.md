# Milestone 3 final review — `ttcap` and the MicroPython PIO+DMA capture

Reviewer: Senior Code Reviewer (read-only pass over `7d9203f..88b72eb`, `final-m3.diff`,
the plan, the three research notes and `progress.md`).
Verification run: `uv run --no-sync pytest -q` → **215 passed, 2 warnings, 17.4 s**.

Scope: `python/ttcap/**`, `python/tests/test_ttcap_*`, `python/tests/test_capture_rp2_pio.py`,
`python/tests/fake_repl.py`, `python/tests/pio_stub.py`, `pyproject.toml`, `README.md`.

---

## Strengths

**The rulings are implemented, consistently, everywhere they touch.**

- *Length-driven reads* (Global Constraint, ledger line 26). `RawRepl.exec_chunks`
  (`repl.py:282-321`) reads `tag[4] + u32 len + payload` and never inspects a payload byte;
  `exec_stream` (`repl.py:248-280`) survives only for text, and the one caller left is
  `throughput.py:114`. The end-of-stdout test — "only the *first* byte of what would be the next
  header can be a non-payload 0x04" (`repl.py:307-313`) — is the correct minimal-lookahead rule,
  and the comment explains why a full 8-byte read would hang on a 3-byte trailer.
  `test_ttcap_exec_chunks.py:36` proves a payload containing 0x04 survives.
- *SHIFT_LEFT + `FLAG_FIRST_SAMPLE_MSB` for both profiles* (ruling C2). `boards.py:32-52`
  (`push_thresh` docstring), `boards.py:64,76` (both profiles), `capture_rp2.py:34-45` (the
  "why the ISR shifts LEFT" block) and `test_capture_rp2_pio.py:137-146` all say the same thing,
  and the test asserts on real instruction encodings (`0x2080, 0x2000, 0x400C`) rather than on
  source substrings.
- *IRQ-handler re-arm* (ruling I1). `on_a`/`on_b` (`capture_rp2.py:358-375`) re-arm before
  flagging, and `test_capture_rp2_pio.py:461-501` enforces both the ordering *and* the
  no-allocation rule (no `BinOp`, no `Call`, no constant ≥ 2^30) that the hard-IRQ heap lock
  demands. This is the best test in the suite: it encodes a hardware fact as a structural
  invariant that a future edit cannot silently break.
- *Cooperative stop* (Task 4 round-2 ruling). `micropython.kbd_intr(-1)` + a `select.poll(0)`
  on `sys.stdin.buffer` between chunk writes (`capture_rp2.py:397-410, 566-589`), with
  `RawRepl.request_stop()`/`interrupt()` split by *intent* rather than by bytes
  (`repl.py:188-210`) so the reader can tell which one a call site meant.
  `test_ttcap_capture.py:334` replays the exact fpga-1 regression (stop mid-chunk, 2183/16388)
  through `FakeChunkBoard(split=64, stop_at_read=3)`.
- *Heap discipline*. `mp.minify()` keeping line numbers (`mp/__init__.py:74-110`) is the right
  trade: the board-side source stays readable and a board traceback still points at the line a
  human would open. `_CLEANUP` importing `gc` **after** the deletion loop (`capture.py:82-89`) is
  a subtle fix and `test_ttcap_capture.py:480` executes the real generated snippet against a
  namespace that already holds `gc`, which is exactly the shape of the tt07 failure.
- *Every non-obvious constant is sourced.* `boards.py:81-95`, `capture_rp2.py:56-76` and
  `capture.py:40-50` cite pico-sdk headers, datasheet sections, MicroPython source lines and
  the board each fact was measured on. `capture_rp2.py:548-550` then **self-checks** the DMA
  register offsets against what `DMA.config()` just programmed — the right answer to a
  controller who quoted the wrong offsets in the dispatch (ledger line 34).
- *Host never re-frames board bytes* (`capture.py:500-502`): the file contains the board's own
  chunk bytes verbatim, so a decode disagreement can never be blamed on host re-serialisation.
  `test_ttcap_capture.py:233` asserts it byte-for-byte.
- *Failure taxonomy is honest.* `CaptureStats.clean` (`capture.py:276-284`) folds overruns,
  RXSTALL, board stderr, host timeout and host error into one predicate; exit code 3 for
  "zero samples" (`cli.py:413-418`) is a genuinely useful distinction.
- README (lines 52-88) documents the Pi `UV_NO_DEV=1` path, the heap floor, the `--frames`
  margin and the `systemctl stop fpgas-tt` rule. `pyproject.toml` keeping numpy/Pillow in a
  `synth` extra is the right response to the Pi 3B+ incident (ledger line 27).

---

## Issues

### Critical

**C1 — `set_gpio_base()` will wipe PIO0's stock firmware program when `--pio 0` is used
on an RP2350 board.**
`python/ttcap/mp/capture_rp2.py:446-456`, reached from `capture_rp2.py:461-462`.

```python
def set_gpio_base(pio, want):
    if gpio_base_is(pio, want):
        return True
    try:
        pio.remove_program()      # <-- no PIO_NUM != 0 guard
```

`main()` guards its *other* `remove_program()` call correctly
(`capture_rp2.py:487-491`: `if PIO_NUM != 0:` … "PIO0 holds the stock firmware's own program
(the FPGA loader) on FPGA boards, so it must be left alone"), but the `set_gpio_base()` path has
no such guard and runs **first**, before the guarded one. On an RP2350 board `GPIO_BASE == 16`,
so any run with `--pio 0` enters `set_gpio_base(rp2.PIO(0), 16)`, and PIO0 is by construction not
at base 16 (`capture.py:44-49` records `rp2.PIO(0).gpio_base(16)` raising EINVAL on fpga-1) — so
`remove_program()` fires unconditionally on the block holding the FPGA bitstream loader.

Nothing stops the user getting there: `capture_cfg()` accepts `0 <= pio <= 2`
(`capture.py:132-133`) and `--pio` is a documented integer flag whose help text
(`cli.py:360-363`) actually *names* block 0, which invites trying it. Recovery needs a board
power cycle — the one operation the Global Constraints ration ("one board at a time", leave the
daemon running), and M5 will be driving these boards for minutes at a time.

There is also a comment/code contradiction here: `capture_rp2.py:485-486` states the rule
("Only PIO_NUM != 0") as if it were global to the script, and it is not.

*Fix (both halves, ~4 lines):*
1. Board side — guard the destructive call:
   ```python
   if PIO_NUM != 0:
       try: pio.remove_program()
       except Exception: pass
   ```
   and have `set_gpio_base()` return `False` for block 0 that is not already in place, so
   `main()` emits its existing `error=PIO0 gpio_base is not 16` TIME chunk instead.
2. Host side — reject it before it ships. In `capture_cfg()` (`capture.py:132`):
   ```python
   if pio == 0:
       raise ValueError("pio 0 holds the stock firmware's own program; use 1 or 2")
   ```
   with a test alongside `test_capture_cfg_rejects_bad_arguments`
   (`test_capture_rp2_pio.py:615`).

### Important

**I1 — the board restores `kbd_intr(3)` 37 lines before it writes the closing `TIME` trailer.**
`python/ttcap/mp/capture_rp2.py:596` vs `capture_rp2.py:625-635`.

```python
finally:
    micropython.kbd_intr(3)          # line 596 — Ctrl-C is an exception again
    ...
    write_time_chunk(out, overrun_total * SAMPLES_PER_CHUNK, summary.encode())   # line 633
    if hasattr(out, "flush"): out.flush()                                         # line 634
```

From line 596 onward a Ctrl-C raises `KeyboardInterrupt` again, and `finally` then does the one
thing the whole cooperative-stop design exists to protect: a multi-byte `out.write()` on a path
where `mp_hal_stdout_tx_strn()` blocks for CDC TX space and runs pending handlers while it waits
(the mechanism `capture_rp2.py:102-111` documents). A Ctrl-C landing in that window truncates the
trailer — reproducing the exact fpga-1 regression the milestone fixed, and losing the *only*
place the overrun and RXSTALL counts exist (`capture_rp2.py:621-624` says so itself).

This is reachable from ttcap's own code, not just from a human: `run_capture`'s timeout and
framing paths call `repl.recover()` (`capture.py:533, 539`), which writes a real Ctrl-C
(`repl.py:224`). A board that was slow rather than dead can be inside its `finally` at that
moment. The docstring at `capture_rp2.py:590-594` even asserts the opposite invariant — "the
host's last-resort second Ctrl-C after `finally` has restored it" — treating the restore as if
it happened after the trailer.

*Fix:* make `micropython.kbd_intr(3)` the **last** statement of `finally`, after
`write_time_chunk`, `flush`, the buffer drop and `gc.collect()`. Keep the `except
KeyboardInterrupt: pass` handler, which still covers a Ctrl-C arriving before `kbd_intr(-1)`.
Add a structural test next to `test_main_cleans_up_in_a_finally_block`
(`test_capture_rp2_pio.py:402`):
```python
finally_src = ast.unparse(...)
assert finally_src.index("write_time_chunk") < finally_src.index("kbd_intr(3)")
```

**I2 — the heap floor is a constant and ignores `buf_words`, which is what actually allocates.**
`python/ttcap/capture.py:62-69` and `capture.py:463-470`.

`MIN_FREE_BYTES = 40_000` is checked once; the script then allocates
`2 * 4 * buf_words` bytes at `capture_rp2.py:496` — 32 KB at the default 4096, 64 KB at
`--buf-words 8192`, 128 KB at 16384. All three pass a 40 KB check. On tt07 (~80-84 KB free
measured, ledger line 43) the 8192 case is a guaranteed failure, and the comment at
`capture.py:64-68` says precisely what that failure looks like: *"twice on tt07 the board printed
`FATAL: uncaught exception` and halted, needing a power cycle. Refusing early is strictly
kinder."* The check does not currently deliver that kindness for any non-default `--buf-words`,
and `--buf-words` is an unvalidated user-facing flag (`cli.py:352-355`, no upper bound).

*Fix:* turn the constant into a function of the request and use it at the call site:
```python
COMPILE_HEADROOM_BYTES = 24_000      # minified script compile + REPL globals, measured on tt07

def min_free_bytes(buf_words: int) -> int:
    return 8 * buf_words + COMPILE_HEADROOM_BYTES
```
`8 * buf_words` is the two buffers; 24 KB is the measured `40_000 - 8*4096` headroom, so the
default behaviour is unchanged and the test at `test_ttcap_capture.py:529` keeps passing with
`mem_free=min_free_bytes(4096) - 1`. Add a case for a large `buf_words` being refused.

**I3 — only two exception types tear the board down; everything else abandons a running script.**
`python/ttcap/capture.py:499-539`.

The `for tag, payload in repl.exec_chunks(...)` loop has `except TimeoutError` and
`except ReplFramingError`, both of which call `repl.recover()`. Nothing else does, and the loop
body can raise at least four other ways:

- `CaptureError` from `_time_fields()` on a short `TIME` payload (`capture.py:404-405`) —
  `test_ttcap_capture.py:583` asserts this propagates, and does *not* assert
  `board.interrupts == 1`, so the gap is baked into the suite;
- `struct.error` from `struct.unpack_from("<I", payload, 0)` (`capture.py:505`) when a `RAW `
  payload is shorter than 4 bytes;
- `OSError` from `out.write()` (`capture.py:501`) — disk full, or the GStreamer sink of M5
  going away;
- a host-side `KeyboardInterrupt` (the operator pressing Ctrl-C on the Pi).

In every one of those the generator is dropped un-exhausted, so the board is still running
`capture_rp2.py` and still writing chunks. `cli.capture()`'s `finally` then sends Ctrl-B
(`cli.py:189`) into a streaming script and closes the link. It does recover eventually — the next
`RawRepl.enter()` sends two Ctrl-Cs, which the still-running script picks up as stop bytes and
exits cleanly — but that is luck, not design, and it will not hold for the long-lived link M5
needs.

*Fix:* one `finally` on the streaming block:
```python
chunks = repl.exec_chunks(script, timeout=chunk_timeout)
try:
    for tag, payload in chunks:
        ...
except TimeoutError as exc:
    ...
except ReplFramingError as exc:
    ...
except BaseException:
    chunks.close()
    repl.recover()
    raise
```
and extend `test_time_chunk_shorter_than_its_fixed_fields_is_an_error`
(`test_ttcap_capture.py:583`) with `assert board.interrupts == 1`.

**I4 — `probe` and `throughput` are outside the CLI's own error contract.**
`python/ttcap/cli.py:381-386`, against the contract stated in `cli.py:13-17`.

`capture` and `png` are wrapped (`cli.py:388-426`); `probe` and `throughput` are bare calls.
A missing device, a board traceback, or a dropped WebSocket prints a Python traceback instead of
the promised *"1 a board, link or tool error"*. `ttcap probe serial:/dev/nope` is the single most
likely first command anyone runs.

Two exception types also escape `CAPTURE_FAILURES` (`cli.py:58-65`) on the `capture` path:
`ast.literal_eval` in `resolve_profile` (`cli.py:130`) raises `SyntaxError` — not an `OSError`,
not a `ValueError` — if the board's stdout carries anything besides the dict repr (a firmware
banner, a leftover print). `probe` (`cli.py:100`) has the same line.

This is also the answer to the "`--profile auto` when the board's `GPIOMap` import fails"
question: the `ImportError` path is handled correctly and tested
(`cli.py:127-129` → `CaptureError`; `test_ttcap_cli.py:51`), but the *malformed reply* path is
not, and the error message does not tell the user the obvious workaround.

*Fix:* wrap all four subcommands in one handler, add `SyntaxError` to `CAPTURE_FAILURES`, and
extend the `--profile auto` message: `"… pass --profile rp2040 or --profile rp2350 instead"`.

**I5 — `RawRepl.upload()` would `NameError` on a real board, and the fake hides it.**
`python/ttcap/repl.py:323-331`; masked by `python/tests/fake_repl.py:55-56`.

```python
self._exec_checked(f"f.write(ubinascii.a2b_base64(b'{encoded}'))")
```

`ubinascii` is never imported on the board. In a fresh raw REPL the demo-board `main.py` leaves
`tt` in globals, not `ubinascii`, so the first chunk write raises `NameError`. The test at
`test_ttcap_repl.py:64` passes only because `FakeRawRepl.__init__` pre-seeds
`{"ubinascii": SimpleNamespace(a2b_base64=base64.b64decode)}` into the board namespace — the fake
is more generous than the board, which is the one thing a fake must never be.

`upload()` is currently dead in the capture path (the script is sent inline through
`exec_chunks`), which is why hardware never caught it — but it is a plan-listed interface
(plan line 81) and M6 is the milestone most likely to want it, for a board-side script too big to
compile from a single raw-REPL line.

*Fix:* `self._exec_checked("import ubinascii")` as the first statement of `upload()`, and delete
the pre-injection from `FakeRawRepl` so the test proves it.

### Minor

| # | Where | What | Fix |
|---|---|---|---|
| M1 | `cli.py:183` | `open(out_path, "wb")` happens *before* `run_capture` can refuse on the heap floor, so a refused run leaves a **zero-byte** `.vgacap`. Contradicts `cli.py:151-153` and `capture.py:456-458` ("a refused run leaves no header-only file behind") — true of content, false of the file. | Do the `prepare_board`/heap check before `open`, or write to a `.part` and rename. Assert `not out.exists()` in `test_capture_prints_the_boards_traceback_…` (`test_ttcap_cli_capture.py:236`). |
| M2 | `repl.py:320` | `length` from the header is used unbounded. A valid tag with a corrupt length buffers until the whole `timeout` expires. | Cap: `if length > MAX_CHUNK_BYTES: raise ReplFramingError(...)`, `MAX_CHUNK_BYTES = 1 << 20`. |
| M3 | `repl.py:302-304` | "`timeout` bounds each individual read, not the whole run" — but `read_exact` (`repl.py:164`) sets one deadline for the whole *n*-byte read. Harmless at 30 s / 16 KB, wrong as written, and it becomes load-bearing for M5's longer buffers. | Either reword, or refresh the deadline whenever bytes arrive (preferred — see R4). |
| M4 | `capture.py:521-523` | When the board stops itself on `MAX_BYTES`, the host still evaluates `_should_stop` on the trailer `TIME` chunk and writes a stop byte to an already-finished script. Harmless (raw REPL treats 0x03 at the prompt as "clear line"), but it is a stray byte on the wire. | Skip the stop once a summary `TIME` (`overruns=`) has been seen. |
| M5 | `capture.py:173-175` | "Chunk headers add 8 bytes per ~16 KB buffer" — it is 12 non-sample bytes per `RAW ` chunk (`tag` + `len` + `sample_count`, `capture_rp2.py:217`) plus every `TIME` chunk, and the board counts all of them in its `sent`. This is the ledger's deferred `frames_to_max_bytes` minor. | Correct the number in the docstring now; the arithmetic can wait (see Triage). |
| M6 | `capture_rp2.py:153`, `capture.py:158` | `SYSCLK_HZ` is assigned from CFG and never read; the authoritative value comes back in the trailer (`capture_rp2.py:631`, `capture.py:33-36`). Dead key costing wire bytes and a board global on an 80 KB heap. | Drop `sysclk_hz` from `capture_cfg()` and the script. |
| M7 | `boards.py:15-19` | `FLAG_FIRST_SAMPLE_MSB = 1` re-declares `vgacap.stream.FLAG_FIRST_SAMPLE_MSB`; the docstring admits it is a mirror. `capture.py:24` already imports from `vgacap.stream`, so there is no layering reason. | `from vgacap.stream import FLAG_FIRST_SAMPLE_MSB`. |
| M8 | `boards.py:55-78` | Both profiles are built with **10 positional arguments**; `RP2040_TT06 = BoardProfile("rp2040-tt06map", 0, (5,6,7,8,13,14,15,16), 0, 5, 12, 12, 2, 1, (...))` cannot be read without counting. M6 adds fields. | Keyword arguments now; consider `@dataclass(frozen=True, kw_only=True)`. |
| M9 | `capture_rp2.py:203-212`, `mp/throughput.py:44-57` | `_write_all` copies `data[pos:]` on the short-write retry — a 16 KB allocation on the heap-tight path. `throughput.py:46-49` documents avoiding this on pass 0 but the retry still copies. | `view = memoryview(data)` then `out.write(view[pos:])`. |
| M10 | `ttcap/mp/*.py` | These are importable module paths (`pyproject.toml` ships `ttcap.mp` as a package) that raise `NameError: CFG` if anything imports them, contradicting `mp/__init__.py:2-9` ("never imported on the host"). Any `pkgutil.walk_packages` consumer trips on it. | Either accept and note it, or wrap the module tail in `if "CFG" in globals():`. |
| M11 | `repl.py:85-87` | `websockets.sync.client.connect()` not used as a context manager → `DeprecationWarning`, visible in the suite output. Ledger's deferred minor. | See Triage — fix for M5. |
| M12 | `throughput.py:113-114` | The clock starts before the `OK` ack, so board-side compile time is charged to the transfer. Ledger's deferred minor. | See Triage — document, do not change. |
| M13 | `capture_rp2.py:378-381` | `STOP_BYTES` accepts `b"q"` as well as `b"\x03"`; nothing in `repl.py`, `cli.py` or the README mentions it. | One README line, or drop `b"q"`. |

---

## Triage of deferred minors

| Ledger item | Verdict | Reasoning |
|---|---|---|
| `websockets` sync `connect()` DeprecationWarning (line 24) | **Fix now (M5)** | Cheap, and M5 is exactly the consumer that makes it matter: the GStreamer element holds one `WebSocketLink` open for minutes on the debug path, and the non-context-manager construction is the API being removed. Wrap it: keep the object but call `connect(url, max_size=None)` inside an `ExitStack` held by `WebSocketLink`, or move to the documented `legacy=True`/context-manager form. Also gives the suite a clean warning-free run so a real warning is visible. |
| Dead `dmas` list in `capture_rp2.py` (line 37) | **Already resolved** | No `dmas` list survives; the script iterates `for dma in (dma_a, dma_b)` (`capture_rp2.py:603, 615, 618`). Strike it from the ledger. |
| `uctypes` import could be guarded (line 37) | **Wait** | `uctypes` exists on every rp2 build the project targets and is used once (`capture_rp2.py:542-543`). A guard would add a branch and a heap name for no measured benefit. Revisit only if a non-rp2 port ever appears. |
| Throughput timing starts before the `OK` ack (line 37) | **Wait, but document** | Changing it now makes the published numbers in `docs/research/2026-09-15-usb-cdc-throughput.md` non-comparable with anything measured later. The bias is one board-side compile (~10 ms against a 1-8 s transfer, ≲1%) and it is conservative — it *understates* KB/s, so the derived `clock_max` is safe. Add one sentence to the research note saying so; change the code only when the note is next re-measured. |
| `frames_to_max_bytes` counts chunk headers, ~0.2% short (line 45) | **Wait; fix the docstring now** | The +2 frame margin (`capture.py:178`) is 840,000 clocks against a 2,600-clock shortfall — three orders of magnitude of cover, and hardware confirmed 1/1/0 frames on tt07 (ledger line 43). Fix the wrong "8 bytes" figure (M5 above) now; correct the arithmetic when M6 touches this function anyway for non-640x480 timing, at which point `CLOCKS_PER_FRAME_640X480` should become a parameter rather than a constant. |

Everything in the **Critical/Important** list above is *new* — none of it was deferred; C1, I1 and
I3 are all regressions of invariants the milestone's own comments assert.

---

## Recommendations for Milestone 5 (GStreamer source + demo)

**Is `run_capture` usable as a stream today? No — for two reasons, both small.**
It takes `out` and writes to it (`capture.py:430, 501`), and `CaptureRequest.__post_init__`
*rejects* the unbounded case outright (`capture.py:217-220`: "seconds and max_bytes are both 0:
the capture would never stop"). A GStreamer element wants exactly that: run until the pipeline
says stop. The chunk loop itself is already the right shape — it is a `for` over a generator that
never buffers more than one chunk — so the refactor is mechanical.

- **R1 — `ttcap.capture.iter_capture()`.** Split `run_capture` at the write:
  ```python
  def stream_header_bytes(req: CaptureRequest) -> bytes:        # Writer into a BytesIO
  def iter_capture(repl, req, *, stop=None, chunk_timeout=DEFAULT_CHUNK_TIMEOUT
                   ) -> Iterator[tuple[bytes, bytes]]: ...
  def run_capture(repl, req, out, chunk_timeout=...) -> CaptureStats:
      out.write(stream_header_bytes(req))
      for tag, payload in session.chunks(): out.write(tag + pack(len(payload)) + payload)
      return session.stats()
  ```
  Keep `CaptureStats` frozen as the final snapshot. Add a mutable `CaptureAccumulator` holding
  the same counters, updated per chunk, so a long-running consumer can read live
  `samples`/`overruns`/`dropped` without waiting for the trailer. `run_capture`'s behaviour and
  every existing test stay as they are.
- **R2 — `CaptureSession`.** Wrap R1 in a class so the element has something to hold across
  `start`/`stop`: `CaptureSession(repl, req)` with `.header_bytes`, `.chunks()`, `.stats()`,
  `.request_stop()` and `.close()`. `.close()` is the home for the I3 fix — close the generator,
  `repl.recover()` if it did not run to completion.
- **R3 — allow an unbounded request.** Add `stop: Callable[[], bool] | None = None` to
  `CaptureRequest` and relax the `__post_init__` check to
  `if self.seconds == 0 and self.max_bytes == 0 and self.stop is None: raise`. Thread it into
  `_should_stop` (`capture.py:423-427`). The board side already supports it —
  `max_bytes=0` means "until stopped" (`capture_rp2.py:16, 586`).
- **R4 — out-of-band stop, and a stop latency worth stating.** `_should_stop` is only evaluated
  *after* a chunk arrives (`capture.py:521`), so stop latency is one DMA buffer — 82 ms at
  750 kHz/4096 words on RP2350, but **2.2 s** at the RP2040's 60 kHz ceiling. For a pipeline
  that is fine; for `EOS` handling it must be documented. If the element needs to stop from
  another thread, `RawRepl` needs a `threading.Lock` around `_link.write` (`repl.py:199, 210,
  224, 239`) — pyserial and `websockets.sync` are not safe for concurrent writes. Add
  `RawRepl._write_lock` and route `request_stop()`/`interrupt()`/`recover()` through it.
  Separately, make `read_exact` refresh its deadline on progress (M3) so a slow bridge cannot
  trip a whole-chunk timeout on a minutes-long run.
- **R5 — a decode adapter, so the element does not re-derive the packing.**
  `ttcap.decode.samples_from_chunk(header, tag, payload) -> Iterator[int]`, built on
  `vgacap.stream.unpack_words` and `_slot` (`python/vgacap/stream.py:35`). The `flags` /
  `samples_per_word` / `signal_map` rules are subtle enough (the whole C2 ruling) that a second
  implementation inside a GStreamer element is how a wrong picture gets shipped.
- **R6 — link exclusivity as a first-class step.** `SerialLink` already passes `exclusive=True`
  (`repl.py:62`), which is right, but the error when `fpgas-tt` holds the device is a bare
  `OSError`. Add `ttcap.pi.daemon_stopped(slug)` — a context manager doing
  `systemctl stop/start fpgas-tt` with a `try/finally` restore (Global Constraint: "always
  restoring it") — and have `link_from_url` name the holder (`fuser -v <port>`) in its message.
  M5 will hit this on every run.
- **R7 — a hardware-in-the-loop CI job.** See the list below; it is the single highest-value
  thing M5 can add, because every defect this milestone actually cost time on was invisible to
  the host tests.

## Recommendations for Milestone 6 (whole-frame capture into SRAM, FRAM chunks)

**Is `capture_rp2.py` too monolithic? Yes, but only just — and the split is clean.**
654 lines / 8.5 KB minified, of which the *streaming* policy is `main()`'s loop
(`capture_rp2.py:562-589`) and the trailer. Everything else is reusable by a frame-capture
script and would otherwise be copy-pasted: `_le32`, `_write_all`, `write_raw_chunk`,
`write_time_chunk`, `dma_reg`, `init_input_pins`, `make_sampler`, `stdin_stream`,
`stop_requested`, `gpio_base_is`, `set_gpio_base`, the register-arithmetic block
(`capture_rp2.py:179-188`) and the hard-IRQ state block. That is roughly 60% of the file, and
duplicating it would also duplicate every hardware fact documented in it.

- **S1 — `ttcap/mp/prelude.py` + `mp.build()`.** Move the shared half into `prelude.py` and add
  ```python
  def build(cfg: dict, *names: str) -> str:   # with_cfg(minify(prelude) + minify(script), cfg)
  ```
  Concatenation, not import: the raw REPL executes one text blob, and `module_level_names()`
  (`mp/__init__.py:113`) and `with_cfg()` already work on concatenated source unchanged.
  `minify()` keeps line numbers *within* each file, so record the prelude's line count in the
  build result if tracebacks need mapping back. This also shrinks the second script's
  contribution to the 80 KB compile problem to near zero.
- **S2 — make the script a request field.** `CaptureRequest.script: str = "capture_rp2.py"` and
  `run_capture`/`iter_capture` reading it (`capture.py:461` is the only place it is hard-coded).
  `frame_rp2.py` then needs no new host flow, only a new CFG.
- **S3 — CFG becomes layered and validated.** `capture_cfg(profile, **extra)` returning the
  board-derived base plus script-specific keys, and `mp.required_cfg_keys(source)` — a trivial
  AST scan for `CFG["..."]` subscripts — checked host-side before the script ships. Today a
  missing key is a `KeyError` traceback at board line 1, after the upload; with M6 adding a
  second key set that becomes a real failure mode.
- **S4 — `BoardProfile` needs room.** FRAM/PSRAM pins, an SRAM budget and probably a
  `frame_clocks` value all belong there. Do M8 (keyword construction) first, then add fields
  with defaults so `WELLAND` and both literals stay one-line edits.
- **S5 — the heap floor must be per-mode.** Whole-frame capture allocates far more than
  2×16 KB. I2's `min_free_bytes(buf_words)` should become `req.min_free_bytes()`, dispatched by
  script — the fix and the M6 requirement are the same change.
- **S6 — teach `run_capture` about `FRAM`.** `repl.CHUNK_TAGS` (`repl.py:31`) already accepts
  it, so a `FRAM` chunk passes framing and is counted in `chunks`, but `capture.py:503-520` only
  branches on `RAW ` and `TIME` — a whole-frame capture would report `samples=0` and the CLI
  would exit **3** ("the sampler never saw a clock edge", `cli.py:413`). Add the `FRAM` branch
  when M6 lands; noting it now so it is not diagnosed twice.
- **S7 — `RawRepl.upload()` will finally be used.** Fix I5 before relying on it; a whole-frame
  script plus prelude may exceed what is comfortable to compile from a single raw-REPL line.

### Hardware-in-the-loop job: what the tests still cannot catch

Every one of these was found on a board during M3 and is invisible to `pytest`. `main()` in
`capture_rp2.py` is **never executed** on the host — `test_capture_rp2_pio.py` lifts individual
functions with `ast` and asserts on `ast.unparse` substrings for the rest
(`test_capture_rp2_pio.py:255-272, 402-518`), so the whole main loop, the stop handshake, the
overrun bookkeeping and the `finally` ordering are structurally checked but never run.

1. The minified script **compiles inside the board's heap** (`MemoryError`, or the
   `FATAL: uncaught exception` halt) — for both boards and for the largest supported
   `--buf-words`.
2. **PIO instruction memory does not leak** across ≥12 consecutive captures (`ENOMEM`,
   ledger line 46) — the regression `capture_rp2.py:611-614` fixes.
3. **`PIO.gpio_base()` agrees with the hardware** on RP2350 (`capture_rp2.py:441-444`: it
   reported 16 while the base was still 0) — assert by reading known bar values off `uo_out`.
4. **RP2350 pad ISO is cleared**: a capture returns non-zero samples at all.
5. **The clock pad was not stolen**: `samples > 0` and `rxstall == 0` — the fpga-1 failure
   where `machine.Pin(clk, IN)` silently stopped the PWM.
6. **Hard-IRQ handlers run with the heap locked** — no "Uncaught exception in IRQ callback".
7. **DMA ping-pong under real DREQ pressure**: at the known ceilings (750 kHz RP2350,
   60 kHz RP2040) `overruns == 0`, and at 75 kHz on RP2040 `dropped == overruns *
   buf_words * samples_per_word` exactly — the accounting the research note proved.
8. **Cooperative stop**: no truncated chunk, and the trailer `TIME` is always present. After
   I1 is fixed, add the specific case of a Ctrl-C arriving *during* the trailer write.
9. **`select.poll()` works on `sys.stdin.buffer`** on the rp2 port (`capture_rp2.py:384-394` is
   reasoning from C source, not from a measurement).
10. **`sys.stdout.buffer.write()` short-write behaviour** — `_write_all`'s retry path
    (`capture_rp2.py:206-212`) has never executed anywhere.
11. **The throughput ceilings themselves**, as a regression gate: a firmware bump that halves
    USB CDC throughput would otherwise show up as a silent overrun storm.
12. **`RawRepl.upload()` against a real board** — never once run on hardware (see I5).

A cheap intermediate step, worth more than its cost: a `FakeMicroPythonBoard` that injects stub
`rp2` / `machine` / `micropython` / `select` / `uctypes` modules into `FakeBinaryBoard(modules=…)`
— the hook already exists (`fake_repl.py:172, 187-189`) and `pio_stub.py` is half of it — and
actually runs `main()` with a fake ping-pong DMA. That alone would cover the stop handshake, the
`FULL`/`OVERRUNS` bookkeeping, the `sent` accounting and the `finally` ordering (I1) as
*behaviour* rather than as substrings.

---

## Assessment

**Ready for Milestone 5: With fixes.**

The milestone did what it set out to do and the evidence is real: captures on both board
families, over direct serial and the bridge, clean to 750 kHz on RP2350 and 60 kHz on RP2040,
exact overrun accounting, a cooperative stop that survives the regression that motivated it, and
215 host tests that pass in 17 seconds. Every ruling in the plan's Global Constraints is
implemented consistently across `boards.py`, `capture.py`, `cli.py`, the two MicroPython scripts
and the tests, and the code carries its hardware reasoning in comments that are — with the three
exceptions below — accurate.

What holds it back is a small set of defects that are all *contradictions between a stated
invariant and the code that implements it*, which is the category most likely to be re-learned
the expensive way:

- **C1** (`set_gpio_base` wipes PIO0) is destructive to shared bench hardware, reachable from a
  documented flag, and the file states the opposite rule three lines away. **Fix before M5** —
  M5 drives these boards for minutes at a time and a power cycle is rationed.
- **I1** (`kbd_intr(3)` before the trailer) re-opens the exact hole the cooperative stop was
  built to close, and ttcap's own `recover()` is one of the things that can walk into it.
  **Fix before M5.**
- **I3** (only two exception types recover the board) becomes structural in M5: a long-lived
  session that leaves a script running on a failure will corrupt the *next* thing the element
  does, not just the current capture. **Fix before M5**, ideally as part of R2's
  `CaptureSession.close()`.
- **I2** (heap floor ignores `buf_words`) is the check failing at the one job it was added to do,
  and M6 makes it worse. **Fix before M5** — it is six lines and S5 needs it anyway.
- **I4**, **I5** and M1-M5 are cheap and should ride along; M6-M13 can wait for the M5/M6
  refactors that touch the same lines.

The architecture for what comes next is in better shape than the issue count suggests. `run_capture`
is one `for`-over-a-generator away from being a streaming source (R1-R3 are mechanical, maybe
80 lines net), and `capture_rp2.py` is monolithic only in the sense that its reusable half has not
been named yet (S1). Neither is a rewrite. The one genuine structural gap is that the board
script's main loop has never been executed anywhere but on a board — worth closing with a stubbed
`main()` harness in M5 alongside the HIL job, because the next two milestones both add board-side
logic and there is currently no way to test it except by shipping it to Welland.
