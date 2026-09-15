# SDD ledger — plan: /home/tim/github/TinyTapeout/tt-vga-capture/docs/superpowers/plans/2026-09-15-m2-stream-and-frame.md

Spec: /home/tim/github/TinyTapeout/tt-vga-capture/docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md (read).

## Pre-flight scan (2026-09-15)

| Pair / task | Produces vs consumes | Finding |
|---|---|---|
| T2 -> T3,T4,T5 | stream.h API (writer/reader structs, event union) | consistent; header committed on main before branching (public header includes all writer functions declared up front) |
| T3 -> T4 | `vgacap_pack_samples`, `unpack_word`, `emit_run` | T4 test uses `vgacap_pack_samples` declared in T3: ok |
| T2/T3/T4 -> T5 | wire layout mirrored in Python | offsets in `test_header_bytes` (data[4]=21 length, data[10]=bits, data[16:24]=map, data[24]=spw, data[26:28]=desc_len) match the format table: ok |
| T6 (frame.h) -> stream.h | `VGACAP_SIG_*` enum | frame.h includes stream.h: ok |
| T6 -> T7,T8 | learner struct fields (`clk_in_line`, `t.mode`, `t.locked`) | ok |
| T7 -> T8 | `vgaframe_t` gains `fram_max_line` in T8 | ok |
| T3/T4/T6/T7 CMakeLists.txt | both chains edit the same file | conflict expected at merge; sections pre-marked in the skeleton; resolve by hand |
| T7 test `auto_crop_when_no_mode_matches` | name says auto crop but asserts the table match wins (800x525 still matches) | self-inconsistent naming; Ruling: keep the assertions (they are correct: mode match is by lengths), rename the test to `table_match_wins_over_odd_porches` — cost if wrong: none |
| T6 timing.c draft | `entering_pulse` computed twice | cosmetic; implementer may simplify; tests are the contract |
| T9 e2e `fram` with frames=3 | tool must emit one frame per counter | covered by T8 semantics (counter change flushes) |

Rulings:
- Ruling: batch Tasks 2-5 into one implementer (branch `stream`) and Tasks 6-8 into another (branch `frame`), run in parallel in separate worktrees — the two chains share only stream.h (already on main) and CMakeLists.txt sections; cost if wrong: a CMake merge conflict to resolve by hand.
- Ruling: Task 1 was done by the controller (repo creation publishes to GitHub; not a subagent action). Commits db44136..2a? on main.

## Progress

Task 1: complete (commits db44136..61cd594 + stream header, controller, no review; skeleton builds and tests pass)
Tasks 2-5 (stream chain): implementer DONE on branch worktree-agent-a79f324c70be66cf8 (commits 9cee1e7..51c41e7, base 0fd4646); ctest 4/4, pytest 6/6. Review dispatched (package review-0fd4646..51c41e7.diff in the worktree's .superpowers dir).
Tasks 2-5: complete (commits 9cee1e7..51c41e7, review clean, merged to main with --no-ff)
Tasks 2-5: minor (deferred): TIME msg_len not checked against chunk length (reader.c); vgacap-dump silent on truncated unknown chunk; sample_mask duplicated in writer.c/reader.c (brief-directed)
Tasks 6-8 (frame chain): implementer DONE on branch worktree-agent-a325ee23c4a060697 (commits d87f8ab..aa2b6c5, base 0fd4646); 16 C tests passing; vgacap_frames.c not wired into CMake yet (needs stream lib, on main now). Implementer concern: learner hsync phase state reset in vgaframe_frame_begin (found via TDD). Review dispatched on opus (package review-0fd4646..aa2b6c5.diff in that worktree).
Tasks 6-8: review — spec ✅ (T8 fallback non-functional), quality Needs fixes. C1 run clip wrap (frame.c:116); I1 crop clamp underflow (frame.c:73); I2 FRAM without force_mode never reassembles (plan defect); I3 raw under-clear after FRAM flush; 12 minors (review file task-6to8-review.md).
Ruling: I2 — in FRAM mode with no forced/learned mode, expected_lines comes from vgaframe_mode_match_cpl(clocks_per_line) (clocks-per-line is unique across the built-in table); if that fails too, fall back to fram_max_line with partial emission on counter change. A future format revision may add lines_per_frame to FRAM. Cost if wrong: non-table timings in windowed mode emit as partial fragments until fixed.
Controller merged main into the frame branch (4dcadae, CMake conflict resolved by keeping both test lists) so the fix round can wire vgacap-frames into CMake and run the Task 7 manual PPM check.
Tasks 6-8: fix round 1/5 dispatched (resume implementer) with C1, I1, I2(+ruling), I3, and the vgacap-frames wiring.
Tasks 6-8: fix round 1 implementer DONE_WITH_CONCERNS (commits 6bc2e14, 9690a78, 6a60a96, c0e5fc7): C1/I1/I2/I3 fixed with regression tests; vgacap-frames wired; found+fixed line_in_frame corruption on mid-frame start. Concern: 2-frame stream starting mid-frame can never reach `locked`.
Ruling: emit gate in continuous mode = learner.t.locked || learner.t.mode != NULL || cfg.force_mode — an exact (cpl, lpf) table match on the first fully measured frame is sufficient evidence. Cost if wrong: a spurious first frame when a wrong initial measurement happens to match a table entry exactly (both numbers), which is unlikely. Also produced a 3-frame simulated stream (tt-vga-testpatterns/tmp/vga_pattern_3f.vgacap) for the manual check.
Tasks 6-8: fix round 1 continued — 15e9e0c implements the emit-gate ruling with two tests; 3-frame simulated stream reconstructs pixel-exact (640x480@60, locked). Parked — Ruling: a capture that starts mid-frame needs one frame boundary plus one full frame before the first emission, so a stream of exactly two frame periods with arbitrary phase yields no complete frame; this is inherent to boundary-based reconstruction, real captures run for several frames; documented in the README (Task 10). Cost if wrong: none for real captures; synthetic tests must use >= 3 periods or aligned starts.
Tasks 6-8: scoped re-review dispatched over 4dcadae..15e9e0c.
Tasks 6-8: fix round 1/5 (6 addressed, 0 open; commits 6bc2e14..15e9e0c)
Tasks 6-8: complete (commits d87f8ab..15e9e0c, review clean after round 1, merged to main --no-ff)
Tasks 6-8: minor (deferred): 12 minors listed in task-6to8-review.md (M1 line_in_frame first-frame bogus lpf was fixed in 6a60a96; the rest untouched)
Task 9: first dispatch landed in the wrong repo worktree (controller cwd was tt-vga-capture); re-dispatched from vgacap. Ruling: none needed.
Task 9: implementer DONE_WITH_CONCERNS (4f20a40): 14 pass / 3 fail — the 3 fram e2e cases fail on printed mode/lpf/vsync only (pixels exact). Confirmed real gap in frame.c emit(): timing handed to the callback ignores the cpl-resolved mode. Ruling: fix in C inside Task 9 (out_timing member populated from the resolved mode; regression tests in test_frame_partial.c). Cost if wrong: none beyond a small metadata change.
Task 9: implementer DONE (4f20a40 python synth/e2e; 49f951c C fix out_timing); 8/8 C, 17/17 py. Review dispatched (package review-7d9203f..49f951c.diff in that worktree).
Task 9: review — spec PASS, quality PASS with one Important (synth.bars uint8 arange wraps past 255); 2 minors. Fix round 1/5 dispatched (resume implementer).
Task 9: fix round 1/5 (2 addressed, 0 open; commit 2c056e4)
Task 9: complete (commits 4f20a40..2c056e4, review clean, merged to main --no-ff)
Task 10: docs done by controller (README sections, stream-format research note); clean rebuild + full tests green on e1aab07. Final whole-milestone review dispatched on opus over 61cd594..e1aab07.
Final review (opus, 61cd594..e1aab07): With fixes. I1 no framing resync/detection after a dropped byte; I2 TIME msg_len and all item counts unchecked vs payload length; I3 fram_mode latches forever (FRAM-then-RAW emits 1 of 4 frames); I4 output API: callback-owned rgb lifetime undocumented, no stride, no documented reset. Deferred minors: only (a) must be fixed now (folded into I2); (b), (c), M5-M11 later.
Ruling I1: keep format v1 (no sync word); add reader resync: after a framing error (unknown tag with non-printable bytes, or length > 16 MiB, or an item-count/length mismatch) the reader emits a non-fatal VGACAP_EV_RESYNC event and scans byte-wise for a known tag followed by a plausible length, resuming there; VGACAP_EV_ERROR stays fatal only for unsupported version. Cost if wrong: a false resync inside sample data after corruption (samples can contain tag bytes); a v2 format with sync word + CRC is noted as future work for the MCU link.
Ruling I3: FRAM mode is per chunk: when a FRAM chunk's sample_count is consumed, further runs are continuous-mode samples (learner-driven), and a pending FRAM accumulation is flushed as partial at the next continuous frame start or on the next frame_begin with a different counter; coverage-complete emission unchanged. Cost if wrong: an extra partial frame at the FRAM/RAW boundary.
Ruling I4: add `stride` (bytes per row) to vgaframe_output_t, document that rgb24 is valid only during the callback and owned by vgaframe, add `vgaframe_reset()` (same as re-init without touching buffers' allocation).
Final fix wave dispatched (one implementer, opus) from acfa997.
Final fix wave: DONE (934d01c, 500e46a, 5b3ea05 on worktree-agent-a31d25c65885ce516); ctest 8/8 (27 tests), pytest 50. Note: implementer used an Opus co-author trailer on its commits; the merge commit carries the standard trailer. Scoped re-review dispatched (opus) over acfa997..5b3ea05.
Interruption: API usage limit killed the final-fix re-reviewer (no work) and the Tasks 2-3 fix implementer (no changes, worktree clean). Re-dispatched re-review (sonnet) and resumed the implementer.
Final fix wave: re-review clean (all four addressed, no new breakage); merged to main --no-ff. Milestone 2 complete. Remaining deferred minors: (c) sample_mask duplication; M5-M11 from task-6to8-review.md; websockets DeprecationWarning (M3 T1).
