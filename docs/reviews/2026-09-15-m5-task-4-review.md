# M5 Task 4 review: `vgacapttsrc` and `vgacapbin`

Base `c25be83` → head `63a3e0d`, 7 commits, reviewed in
`/home/tim/github/TinyTapeout/vgacap/.claude/worktrees/agent-a1c817beb65f73c56`
(read-only; a throwaway `build-review/` was used and deleted).

**Reproduced independently**, in a fresh build directory:

- `cmake -S . -B build-review -G Ninja && cmake --build build-review` — clean,
  with `-Wall -Wextra -Werror -Wshadow` confirmed on the actual compile line.
- `ctest --test-dir build-review` — **12/12 pass**.
- `uv run pytest gst/tests -v` — **41 passed** in 19 s (the report says 39; two
  more have since been parametrised).

Hardware results are taken as given from the controller and are not re-argued.

---

## Spec compliance

| requirement (plan Task 4 + controller dispatch) | verdict |
|---|---|
| `GstPushSrc` spawning `ttcap capture --out -`, pushing ~64 KiB `application/x-vgacap` | met — `GST_TYPE_PUSH_SRC`, blocksize 65536, caps `application/x-vgacap` |
| properties `link`, `project`, `design`, `clock-hz`, `profile`, `pio`, `buf-words`, `seconds` | met, all present with the pinned defaults |
| `ttcap-command`, shell-split | met — `g_shell_parse_argv`, default `uv run --no-sync ttcap` |
| `stop-timeout` | met, default 15 s |
| cooperative stop: SIGINT, wait up to `stop-timeout`, then SIGKILL | met, and better than asked (drain + pipe-close rung between) |
| tolerates ~2.2 s board latency at 60 kHz | met — default 15 s, blurb says to allow one DMA buffer; test asserts the element waits out a simulated 0.5 s latency |
| child stderr on a second pipe, surfaced as log messages | met — helper thread, `GST_INFO` per line, 8×200-byte tail |
| non-zero exit ⇒ `GST_ELEMENT_ERROR` with the last stderr lines, not silent EOS | met — `child_finished()`; test asserts the child's own two stderr lines reach the bus |
| `vgacapbin` parses `tt-serial://`, `tt-ws://`, `file://`, query → source properties, ghost pad | met (plus `tt-wss://`); ghost pad exists from `init()` so `gst-launch` can link in NULL |
| both elements registered | met — `gstvgacap.c` registers all three |
| `-Wall -Wextra -Werror -Wshadow` clean | met (verified on the real compile command) |
| tests: frame counts, property propagation, prompt stop with no zombie, non-zero exit ⇒ pipeline error, garbage does not hang, URI parser incl. bad URIs | met — all six present and passing; frames are compared **against the fake's own bytes**, which is stronger than the requirement |

Two cosmetic deviations from the plan's literal text, neither a defect:
the plan's example query is `?clock=...` while the implementation (correctly)
wants `?clock-hz=...` and errors loudly on `clock`; and `tt-wss://` is a
superset the plan did not ask for.

**Spec verdict: PASS.**

---

## Stop sequence verdict

**The design is right and the drain is the load-bearing, non-obvious part — but
the sequence ends in an unbounded `g_thread_join` that can hang teardown for
ever, and the group SIGKILL is skipped exactly when it is most needed.**

What holds up:

- **Signalling the process group is correct and cannot hit anything it should
  not.** `child_setup()` does `setpgid(0,0)`, so the pgid *is* the child's pid;
  while that leader is alive no other group can carry that id, so `kill(-pid)`
  can only reach descendants of our own spawn. `signal_child()` guards on
  `!reaped`, so it never signals a recycled pid. The ESRCH fallback to
  `kill(pid)` correctly covers a host where `setpgid` did not take.
- **The `uv run` hop works — I tested it, the implementer could not.** Running
  the stop probe with `ttcap-command="uv run --no-sync python fake_ttcap.py …"`:
  `{"buffers": 11, "stop_seconds": 0.557, "child": "gone"}`, and the fake's
  copy ends `TIME t=… dropped=0`. SIGINT to the group reached the grandchild
  through `uv run`, the grandchild is gone, and the stream is well formed. That
  open concern is closed.
- **Steps 1 and 3 rest on verified `ttcap` behaviour, not hope.**
  `python/ttcap/cli.py:383-420` turns the first SIGINT into a cooperative stop;
  `cli.py:265-290` and `cli.py:790-812` make `BrokenPipeError`/`ConsumerClosed`
  the normal end of a stream with exit 0. So the "close the pipe" rung really
  does produce a clean exit rather than a bus warning.
- **The drain-then-close-then-kill order cannot lose a trailer that would
  otherwise survive.** The only loss window is deliberate and documented: a
  trailer written after `stop-timeout` expires dies with the pipe. Everything
  earlier is drained (and discarded — see Minor 3), the child is never blocked
  on a full pipe, and `drain_stdout()` returning at its 1 MiB cap hands the
  deadline back every sweep.
- **`stop()` is safe to call twice and safe with no child.** `stop_child()`
  returns on `!have_child`, `close_fd()` tolerates -1, the pool and thread are
  NULL-checked. `GstBaseSrc` will not call `stop()` after a failed `start()`,
  which is why `start()` calls it itself on the pool-config path — correct, and
  the double call that path could create is harmless.
- **A child that ignores SIGINT is handled** and tested (rungs 2 and 3), as is
  one deaf to both.
- **No use-after-free from `create()` returning mid-stop.** `GstBaseSrc`
  unlocks and stops the streaming task before `stop()`, so nothing races the
  `close(out_fd)` in step 3. This is an assumption worth the comment it already
  has; the `self->stopping` checks inside `create()` are consequently dead code.

What does not (see Important 1 for detail and a reproducer): once the *leader*
is reaped, `signal_child()` returns without signalling, so a descendant still
holding the pipes is never killed; and `stop()` then blocks for ever in
`g_thread_join()` waiting for a stderr EOF that will not come. The same hole is
reached by the `"the capture process %d will not die"` branch — which a USB
serial device wedged in D state can produce on real hardware.

---

## Findings

### Important

**1. `stop()` can hang for ever; an orphaned grandchild is never killed.**
`gst/gstvgacapttsrc.c:410` (`signal_child`), `:474-477`, `:626`
(`g_thread_join`).

`signal_child()` refuses to act once `self->reaped` is set. So if the direct
child exits but any process in its group still holds the pipes, the SIGKILL
rung is skipped, `stop_child()` returns "gone", and `gst_vgacapttsrc_stop()`
then calls `g_thread_join(self->err_thread)` — a join with no deadline, which
can only return when *every* holder of the stderr write end is gone. The same
dead end is reached from the `will not die` branch at `:474`, where the code
logs and falls through to the identical unbounded join. The header's promise —
"The child is reaped in every path, so the element never leaves a zombie
behind" — and the README's "Every path reaps the child" do not hold.

Reproduced. With `ttcap-command` pointing at a wrapper that starts the fake in
the background and exits (`--deaf`, `stop-timeout=3`), `pipeline.set_state(NULL)`
never returned; after 90 s:

```
tid=1719213 name=python3            wchan=futex_do_wait     <- g_thread_join
tid=1719221 name=vgacapttsrc-std    wchan=anon_pipe_read    <- read(err_fd)
```

and the grandchild was still running, still holding the (simulated) board — I
had to `kill -9` it by hand.

Why it matters beyond a contrived wrapper: the shipped default is `uv run
--no-sync ttcap`, i.e. a *grandchild* by construction. I verified the happy path
is fine (uv waits and the group signal reaches ttcap), but any interleaving where
the wrapper dies first — a second Ctrl-C, uv being killed, `ssh host ttcap`, or
simply a `ttcap` stuck in D state on a USB serial ioctl so SIGKILL does not take
promptly — turns a pipeline teardown into a permanent hang, with the board held.

Fix (small, two parts):
- Do not gate the *group* kill on `reaped`: while any member remains, the pgid
  is reserved, so `kill(-pid, SIGKILL)` after reaping the leader is safe and
  returns ESRCH when the group is empty. Send it before joining whenever
  `out_fd`/`err_fd` are still open after the leader is gone.
- Bound the join: give `err_thread_func()` a `poll()` over `err_fd` plus a wake
  pipe (the element already has the self-pipe idiom), signal it from `stop()`,
  and join with the same escalation grace. Detaching the thread instead is not
  enough — it would touch `self` after finalize.

**2. A `vgacapbin` URI is arbitrary command execution.**
`gst/gstvgacapbin.c:179-186` + `set_from_string()` at `:82`.

The query loop sets *any* property the source happens to have, by name, and
`ttcap-command` is one of them. Reproduced (harmlessly):

```
gst-launch-1.0 vgacapbin \
  uri='tt-serial:///dev/fake?clock-hz=60000&ttcap-command=/bin/sh%20-c%20"touch%20…/pwned;%20exec%20cat%20/dev/null"' \
  ! fakesink
```

exited 0 with `Got EOS`, and `tmp/review/pwned` existed afterwards.

Today the URI comes from the operator's own shell, so the blast radius is nil.
But Task 5 is `ttcap demo` **and a browser view**: the moment a URI can arrive
from a form field, a saved playlist, a query string or a shared demo link, this
is remote code execution, and the URI parser's own test even exercises
`?ttcap-command=…` as a supported case. Fix before Task 5 lands: allow-list the
query-settable properties (the board-tuning set — `project`, `design`,
`clock-hz`, `profile`, `pio`, `buf-words`, `seconds`) and refuse
`ttcap-command` (and arguably `link`/`location`, see Minor 9) from a query with
a clear error. Leave `ttcap-command` settable as an element property only.

**3. A PAUSED pipeline corrupts a live capture, and nothing warns.**
`gst/gstvgacapttsrc.c` (element docs) and `README.md` (new `vgacapttsrc`
section).

The implementer raises this in the report but it reached neither the README nor
the element docblock, so the only place it is written down is a file nobody
running the demo will read. I measured it: with the pipeline PAUSED for 4 s the
child wrote exactly **65548 bytes** and then blocked — one pipe buffer of grace,
nothing more. On a real board that is ~90 ms at 750 kHz and ~1.1 s at 60 kHz
before the DMA buffers start overrunning, and the only report of those overruns
is the closing `TIME` chunk, which `stop()` drains and discards (Minor 3), so
the operator gets a silently corrupt capture.

Refusing PAUSED is not the fix — `gst-launch` and every `GstPipeline` pass
through it. Documenting it loudly is: a paragraph in the README's stopping
section and in the element docblock saying a live capture must go straight to
PLAYING and be stopped rather than paused, and that a pause of more than a
fraction of a second will show up as overruns. Optionally, a
`GST_ELEMENT_WARNING` when the element re-enters PLAYING having been paused
while started would make it impossible to miss. Documentation alone is an
acceptable close for this milestone; leaving it in a task report is not.

### Minor

1. **`create()` can block for `stop-timeout` and ignore `unlock()`.**
   `gstvgacapttsrc.c:677` — `child_finished()` calls `wait_for_child(...,
   drain=FALSE)`, which only `g_usleep()`s; the wake pipe is not polled. A child
   that closes stdout but lingers stalls the streaming thread for up to 15 s
   with no way to interrupt it, which is exactly what `unlock()` exists to
   prevent. Use a much shorter grace here (this is not the cooperative-stop
   deadline), or poll the wake pipe alongside.
2. **`unlock()` touches `wake_fds[1]` unlocked while `stop()` closes it.**
   `:651-654` vs `:631-632`. `unlock()` can be driven by a FLUSH_START from an
   application thread, concurrently with a state change running `stop()`; the
   window writes to a possibly-reused fd. Guard with a mutex, or keep the wake
   pipe (or an eventfd) open for the object's lifetime and close it in
   `finalize()`.
3. **The trailer is drained and thrown away.** `drain_stdout()` at `:349`
   discards everything it reads, so for a `seconds=0` capture the closing `TIME`
   chunk — the only overruns/RXSTALL report — never reaches downstream or the
   bus. It survives only as an `INFO`-level log line, because `ttcap` also
   prints its stats to stderr (`cli.py:_report` with `stream=say`). The README's
   "writes its closing `TIME` chunk" reads as if the pipeline receives it.
   Either say so plainly, or post the stderr tail as an element message on a
   clean stop so overruns are visible without `GST_DEBUG`.
4. **`buf-words=0` is silently "use ttcap's default".** `:301` tests
   `buf_words > 0` while `:299` tests `pio >= 0`; 0 is inside the declared
   `-1 … 2^24` range. Make the range `-1` plus `1 …`, or treat `0` as an error.
5. **`profile` is a free string but `ttcap` takes `{rp2040,rp2350,auto}`.**
   `fake_ttcap.py:134` does not mirror the choices, so
   `test_the_element_builds_the_capture_command_it_promises` asserts
   `profile=demoboard` — a value the real CLI rejects. That undercuts the
   fake's stated contract ("exactly the flags `ttcap capture` takes"; it is also
   missing `--no-stop-clock`). Make `profile` a GEnum, or at minimum give the
   fake the same `choices=`.
6. **The README's own `vgacapbin` examples will not run.** The three lines under
   "a URI in, video out" are unquoted (`uri=tt-serial:///dev/ttyACM0?project=…&clock-hz=…`),
   which the controller's hardware session showed is a `gst-launch` parse error
   because of the `?` and `&`. The earlier example in the same file does quote;
   make these match, and add one sentence saying why.
7. **One new `-Wconversion` warning hides under the directory-wide exemption.**
   `gstvgacapbin.c:119` — `gint i` passed to `gst_structure_nth_field_name()`'s
   `guint`. I checked: `gstvgacapttsrc.c` and `gstvgacapuri.c` are
   `-Wconversion`-clean, and the bin has exactly this one hit. The exemption's
   comment claims the only hits are inside GStreamer's own headers "where there
   is no call site to fix"; that is now untrue. (The exemption predates this
   diff, so this is a one-line fix, not an architecture complaint.)
8. **`self->source` is read and written outside the object lock.**
   `gstvgacapbin.c:266` and `:288`, while `change_state` may be in
   `build_source()`/`drop_source()`. Narrow, but free to fix.
9. **A query parameter can override the URI's own authority.** `?link=…` is
   applied after the parsed `link`, so `tt-ws://a:8765/serial?link=serial:/dev/x`
   silently captures from somewhere else. Covered by the allow-list in
   Important 2.
10. **Dead defensive code.** The `self->stopping` branches in `create()` (`:756`)
    and `child_finished()` (`:675`) are unreachable, because the task is always
    stopped before `stop()` sets the flag. Harmless, but they suggest a race
    that does not exist; a comment or removal would read better.
11. **The bin's `link` getter loses the URI-derived value.** After
    `drop_source()`, `get_property("link")` falls back to `wanted`, which never
    saw the link — I measured `""` after two successful runs. Cosmetic.
12. **`SIGPIPE`-on-close is reported as a failure for a non-Python child.** The
    pipe-close rung assumes the child ignores SIGPIPE (Python does). A child
    that does not dies with signal 13, `killed` is FALSE, and `stop_child()`
    raises `GST_ELEMENT_WARNING("ended badly")`. Not a problem for `ttcap`;
    worth one line of comment given `ttcap-command` is user-supplied.

---

## Judgement on each raised concern

| concern | judgement |
|---|---|
| POSIX-only by design | Accept. Declared in the header, the boards hang off Linux hosts, and a Windows port would need a different mechanism entirely. Not worth abstracting now. |
| default `uv run` inherits the pipeline's cwd | Accept. Documented in the README, and a `working-directory` property would be speculative. The absolute-path escape hatch is real and tested. |
| a PAUSED pipeline will make a real board overrun | **Partly reject: fix the documentation now.** Measured at exactly one 64 KiB pipe buffer of grace. Refusing PAUSED would be wrong, but leaving the warning only in a task report is not enough with a board on the other end. See Important 3. |
| the drain's 1 MiB sweep cap is a guard no test forces | Accept, and the honesty is a credit. A Python writer cannot keep the pipe non-empty against 16 KiB reads; the cap is cheap insurance for a faster writer and the test comment says exactly that rather than claiming coverage. Leave it. |
| SIGINT through the `uv run` hop is untested | **Closed: I tested it and it works.** Group SIGINT through `uv run --no-sync` stopped the grandchild in 0.56 s, left nothing behind, and the stream ended with its TIME trailer. But see Important 1 for the case where the hop's *parent* dies first. |
| signalling the process group — could it hit the wrong processes? | **No.** The pgid equals the live leader's pid, so no unrelated group can share it, and `signal_child()` never fires after reaping. The ESRCH fallback is correct. The only defect is the opposite one: it signals too *little* (Important 1). |
| can drain-then-close-then-kill lose the trailer? | **No new loss.** The only window is the deliberate one after `stop-timeout`. Note that the element discards the trailer regardless (Minor 3). |
| `stop()` twice, or with no child? | **Safe.** Fully idempotent; the `start()`-failure path that creates the double call is correct. |
| a child that ignores SIGINT? | **Handled and tested** by rungs 2 and 3. |
| `create()` returning mid-stop — use-after-free? | **No.** `GstBaseSrc` stops the streaming task before `stop()`; nothing races the `close(out_fd)`. The lone unsynchronised edge is `unlock()` vs the wake-pipe close (Minor 2). |
| does the URI parser reject malformed input safely? | **Yes, and unusually well.** `NULL`, empty, no scheme, foreign scheme, `serial:` mistaken for a URI, missing device/host/path, a fragment, userinfo, a cross-host `file://`, and `%zz` are all refused with the right error code, and the C test asserts every refusal quotes the offending URI. Query values are converted with `gst_value_deserialize`, so `clock-hz=sixty` and `nonesuch=1` are pipeline errors, not silent no-ops — I re-ran both. The one thing it does *not* reject is a query naming a dangerous property (Important 2). |

---

## Strengths

- The stop sequence is genuinely thought through, and the drain is the part
  most implementations would omit. The "test the test" evidence — removing the
  drain makes both stop tests fail at *exactly* the full timeout — is the right
  kind of proof and is rare to see offered.
- Verified `ttcap`-side behaviour underpins every rung: the cooperative SIGINT
  handler and the `BrokenPipeError`/`ConsumerClosed`-is-exit-0 path are real
  code in `python/ttcap/cli.py`, not assumptions.
- Isolating the URI grammar into a GLib-only translation unit so the whole good
  and bad table runs as a plain C test, with no registry, pipeline or board, is
  an excellent structural call — and the eleven cases earn it.
- Frames are compared against the fake's **own byte-for-byte copy**, so the test
  cannot pass by two generators agreeing with each other.
- The mirrored-property drift guard (comparing the two elements' `gst-inspect`
  blocks name for name) is a neat answer to a problem GObject creates.
- Buffer pool is `min=4, max=0`, so a `queue` downstream cannot deadlock
  `create()` on acquire — easy to get wrong in the other direction.
- `g_ascii_formatd` for `--seconds`, `FD_CLOEXEC`+`O_NONBLOCK` on the wake pipe,
  the fixed-size lock-protected stderr tail, splitting rather than dropping an
  overlong stderr line, `try_reap()` remembering the real status: a lot of small
  things are right.
- The self-review section changed real bugs (the 4 KiB drain, the uninitialised
  struct on the URI error path, the `start()`-failure orphan, the leaked pad
  template) and is candid about what is not covered.

---

## Verdicts

- **Spec compliance: PASS.** Every item in the plan and the controller's
  dispatch is present, and several are done better than asked.
- **Quality: PASS with required fixes.** The code is careful and the tests are
  strong; nothing here suggests the design is wrong. But Important 1 is a
  reachable unbounded hang that contradicts the element's own stated guarantee,
  and Important 2 becomes a remote-code-execution path the moment Task 5's
  browser view can supply a URI. Both should land before Task 5; Important 3 is
  a documentation change that costs minutes.
- **Stop sequence: sound design, incomplete escalation** — right signal, right
  target, right order, verified through `uv run`, but it stops signalling once
  the leader is reaped and then joins the stderr thread with no deadline.
