# SDD ledger — plan: 

Spec: tt-vga-capture/docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md (read).

## Pre-flight scan (2026-09-15)

| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T1 -> T2,T3,T4 | BoardProfile, RawRepl (exec, exec_stream, upload) | consistent |
| T3 -> T4 | capture_rp2.py CFG dict keys; rxf_addr/rx_dreq helpers in boards.py | T3 defines them; T4 consumes: ok |
| T2, T5 | hardware measurements on Welland Pis | controller runs the hardware steps (SSH/daemon control); implementers deliver code |
| M2 Task 9 | python/vgacap/* | disjoint from python/ttcap/*: safe to run T1 in parallel |

Rulings:
- Ruling: hardware-touching steps (stopping fpgas-tt, running on the Pis) are done by the controller, not subagents, because they change shared infrastructure state; subagents deliver code + host-side tests. Cost if wrong: slower turnaround.

## Progress

Task 1: implementer DONE on branch worktree-agent-a6830c30e613916f5 (commits 61760d9..fa7ffb4, base 7d9203f); 12/12 ttcap tests. Review dispatched.
Task 1: review — spec PASS, quality PASS WITH ISSUES: Important exec_stream drain stops at first '>' (repl.py:150-156); 6 minors. Fix round 1/5 dispatched (resume implementer) with the Important plus minors 1-5 (tests for stderr/split reads/WS/enter twice, timeout buffer reset, ConnectionClosed).
Task 1: fix round 1 implementer DONE (8834d59, ad97339, 2d819b2, 1721545); 19 ttcap tests. Scoped re-review dispatched over fa7ffb4..1721545.
Task 1: fix round 1/5 (6 addressed, 0 open; commits 8834d59..1721545)
Task 1: complete (commits 61760d9..1721545, review clean, merged to main --no-ff)
Task 1: minor (deferred): websockets sync connect() DeprecationWarning (not used as context manager)
Tasks 2-3: dispatched as one implementer (opus) on a vgacap worktree: throughput script + ttcap throughput, capture_rp2.py + host tests + capture_cfg. Hardware runs by the controller afterwards.
Tasks 2-3: implementer DONE (27db7fb, 228127a, decee8e, 50f28b4; 78 py tests). Concern: raw REPL 0x04 terminator is unescaped -> exec_stream truncates binary payloads. Ruling: Task 4 reads the board's output length-driven (parse chunk tag+length, read exactly length bytes; a chunk header starting with 0x04 marks end of script output, followed by stderr and the prompt); exec_stream stays for text-only uses. Cost if wrong: none; the framing already carries lengths. Review dispatched (opus) over acfa997..50f28b4.
Hardware note: cloning vgacap on pi-sw2-p7 and running `uv sync` started a numpy/Pillow source build that made the Pi 3B+ unresponsive (pings ok, SSH/daemon hang). numpy/pillow moved to an optional 'synth' extra (63c1110). The Pi needs a power cycle (allowed, one at a time).
Task 1 (post-merge bug): cli.py probe() runs 'print(GPIOMap.all())' without importing GPIOMap; worked earlier only because a throwaway probe had imported it into the board namespace. Fix: 'from ttboard.pins.gpio_map import GPIOMap' in the exec. To be folded into the Tasks 2-3 fix round or Task 4. Pi env now works: UV_NO_DEV=1 uv sync; uv run --no-sync ttcap ...
Tasks 2-3: review — T2 PASS, T3 FAIL. C1 asm_pio clears globals (CFG constants NameError on board); C2 SHIFT_RIGHT+push 24 leaves valid bits in [31:8]; I1 DMA re-arm race can hang silently; I2 no try/finally (channels leak); I3 input pads not initialised (RP2350 isolation); 13 minors.
Ruling C2: use SHIFT_LEFT for both profiles with flags=FIRST_SAMPLE_MSB (RP2040: 12-bit x2 at push 24 -> bits 23:0 with sample0 in 23:12; RP2350: 8-bit x4 at push 32 -> sample0 in 31:24). Zero extra PIO instructions; matches stream format v1. Cost if wrong: a wrong picture that the host-side ISR simulation test would catch first.
Ruling I1: re-arm the finished channel from inside its IRQ handler (or via mem32 writes to WRITE_ADDR/TRANS_COUNT without trigger); overrun = flag already set when the handler fires again. Cost if wrong: one buffer of latency; overruns reported, never silent.
Fix round 1/5 dispatched (resume implementer) with C1, C2, I1, I2, I3 + the cli.py probe import bug.
Interruption: API usage limit killed the final-fix re-reviewer (no work) and the Tasks 2-3 fix implementer (no changes, worktree clean). Re-dispatched re-review (sonnet) and resumed the implementer.
Tasks 2-3: fix round 1 implementer DONE (6768cdf, 3ea3302, f0b9e50, 34613a9; 103 py tests). Controller error caught: the dispatch quoted CH0_WRITE_ADDR=+0x08/TRANS_COUNT=+0x0c; correct is READ_ADDR +0x00, WRITE_ADDR +0x04, TRANS_COUNT +0x08, CTRL_TRIG +0x0c (RP2040 datasheet 2.5.7). Implementer used the correct offsets and added a read-back self-check. Scoped re-review dispatched over 50f28b4..34613a9.
Tasks 2-3: fix round 1/5 (6 addressed, 0 open; commits 6768cdf..34613a9)
Tasks 2-3: complete (commits 27db7fb..34613a9, re-review clean, merged to main --no-ff)
Tasks 2-3: minor (deferred): dead `dmas` list in capture_rp2.py; uctypes import could be guarded; throughput timing starts before OK ack.
Task 4: implementer DONE + fix round 1 (fc01242..a1dbbb9; 173 py tests). Controller ran the branch's `ttcap capture` on fpga-1 via the bridge: 4,816,896 samples, 294 chunks, overruns=0, 9 complete 640x480@60 frames. Defect seen: Ctrl-C can interrupt the board mid-chunk (payload truncated at 2183/16388 bytes, then the 0x04 terminator), so the host timed out (45 s for a 10 s capture). Ruling for fix round 2: the board disables Ctrl-C (`micropython.kbd_intr(-1)`) while capturing and polls stdin between chunks for a stop byte (host sends b'\x03'); re-enable in finally; the host treats a truncated final chunk as a warning (skip to terminator) rather than a 30 s timeout. Review dispatched (opus) over 5893c61..a1dbbb9.
Task 4: review — CHANGES REQUIRED: C1 Ctrl-C mid-chunk (matches the hardware run), I2 ui_in pads reconfigured on RP2040, I3 no --max-bytes/--frames, I4 CLI exceptions escape; 12 minors. Fix round 2/5 dispatched (resume implementer) with the cooperative stop-byte protocol ruling (kbd_intr(-1) + stdin poll between chunks).
Task 4: fix round 2 implementer DONE (e41a2db; 184 tests). Hardware check on fpga-1: 10.03 s capture, 4,784,128 samples, closing TIME chunk present, 9 frames, no timeout. Scoped re-review dispatched over a1dbbb9..e41a2db.
Task 4: fix round 2/5 re-review clean (C1, I2, I3, I4 addressed). Hardware: fpga-1 clean 10 s capture; tt07 (RP2040) time-based captures fine, but byte-limited runs failed at script start with MemoryError (6934 bytes) or `FATAL: uncaught exception` (board halt, two power cycles). Diagnosis: 25 KB script compile vs ~80 KB free heap with leftovers, fragmentation-dependent; after deleting leftover globals + gc.collect the same command succeeded. Ruling (round 3): minify the uploaded script preserving line numbers (<10 KB), cleanup + gc.collect + mem_free before each run, script frees its objects in finally, frames margin = 2 extra frames. Fix round 3/5 dispatched.
Task 4: fix round 3 implementer DONE (5265779; minify 26.5->8.5 KB, prepare_board, MIN_FREE_BYTES, frames margin 2). Hardware: prepare_board fails on tt07: the cleanup pops 'gc' (an import name) then calls gc.collect() -> NameError. Fix round 4/5 dispatched.
Task 4: fix round 4 DONE (b9cc1c6). Hardware: tt07 3x --frames 1 captures OK (1,257,472 samples each, mem_free ~83 KB, frames 1/1/0), fpga-1 8 s OK (7 frames, mem_free 397 KB). Note: 1,257,472 < 1,260,000 target samples -> margin should round up to whole chunks. Scoped re-review of rounds 3-4 dispatched over e41a2db..b9cc1c6.
Task 4: rounds 3-4 re-review clean. Task 4: complete (fc01242..b9cc1c6, merged to main --no-ff).
Task 4: minor (deferred): frames_to_max_bytes counts chunk headers in the byte target so the sample count lands ~0.2% short (1,257,472 vs 1,260,000); use payload bytes or add header overhead.
Task 4b (follow-up): PIO program leak (ENOMEM after ~10 runs) + CLI overrun line coalescing dispatched to a small fix agent.
Task 4b: review clean; merged to main --no-ff. Hardware: board with full PIO memory recovered, 3 clean runs.
M3 final review (opus): With fixes. C1 set_gpio_base removes programs on PIO0 (wipes the FPGA loader with --pio 0); I1 kbd_intr(3) restored before the TIME trailer; I2 MIN_FREE_BYTES ignores buf_words; I3 run_capture abandons a streaming board on non-timeout errors; I4 probe/throughput unwrapped, SyntaxError escapes; I5 upload() lacks `import ubinascii`. Must-fix minors: M1 zero-byte file on heap refusal, M2 uncapped chunk length, M5 docstring figure, websockets connect() deprecation. M5/M6 recommendations (iter_capture/CaptureSession, mp.build prelude, FRAM handling in run_capture, FakeBinaryBoard) go to the M5 plan. Fix wave dispatched.
M3 final fix wave: DONE (a475ccb..6f576ee on m3-final-fixes; 260 tests). Hardware: --pio 0 refused host-side for rp2350; fpga-1 8 s clean (7 frames); tt07 --frames 1 clean (1,261,568 samples, 1 frame). Scoped re-review dispatched.
