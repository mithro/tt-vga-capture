# M5 Task 5 review — `ttcap demo` and the browser view

**Diff:** `6cb248a..1326ade`, 7 commits.
**Reviewed in:** `/home/tim/github/TinyTapeout/vgacap/.claude/worktrees/agent-a5f9b88117c5f2e7f` (read-only; no commits, no index changes).
**Everything below was run against `gst/tests/fake_ttcap.py` with
`GST_PLUGIN_PATH=$PWD/build`.** No board and no tunnel was touched. (One
early command of mine omitted `--dry-run` and so attempted a TCP connection
to `10.21.2.7:8765`; it timed out with 0 bytes captured, no board was
reached, and the output is reported below as the "no tunnel" case.)

**Verdicts: spec PASS. Quality — CHANGES REQUESTED.**

---

## Spec compliance

| requirement | verdict | evidence |
|---|---|---|
| `--board` resolves through `WELLAND` | **met** | `demo.py:254` `resolve_link`; `--board tt07` → `ws://10.21.2.7:8765/serial`, `--board fpga-1` → `…10.21.2.33…`; all ten slugs covered by `test_every_welland_slug_resolves` |
| `--link` overrides | **met** | `demo.py:266`; verified with `--link serial:/dev/null` |
| tunnel hint when a workstation cannot reach the bench | **met, but the command it prints cannot be run** | `demo.py:208`; see F6 |
| PNG and video on by default | **met** | fresh run wrote `frame-0000..0005.png` + `capture.mkv` 45.8 KiB with no output flags |
| `--window` | **met** | branch built at `demo.py:456`; headless caveat in F9 |
| `--serve PORT` → MJPEG + trivial stdlib index page | **met** | `mjpeg.py`, stdlib only (`http.server`, `queue`, `threading`, `os`); `/` returns the page, `/stream.mjpg` returns `multipart/x-mixed-replace; boundary=vgacapframe` |
| `tee` so one capture feeds every output | **met** | one `vgacapttsrc ! vgadecode ! tee name=t` with four `t.` branches; verified all four at once |
| `--dry-run` prints the pipeline and touches nothing | **met, verified** | with `--serve 8848 --window`: outdir *not* created, port 8848 still bindable afterwards, exit 0, pipeline on **stdout** |
| progress incl. the detected mode from `vgacap-timing` | **met** | `mode 640x480@60: 800 clocks/line, 525 lines/frame, hsync negative, vsync negative, glitches 0`, then `N frame(s), Ns elapsed` |
| Ctrl-C stops cleanly; board winds down; video finalised | **met, verified** | see "Ctrl-C" below |
| source built programmatically, `ttcap-command` as a property, never a URI | **met** | no `uri` token anywhere in `demo.py` except the docstring explaining why; `test_the_source_is_named_and_set_by_property_never_by_uri` |
| tests driven by the fake `ttcap` | **met** | `uv run pytest -q` → **409 passed, 1 skipped**; `uv run pytest gst/tests -q` → **47 passed**. Both match the report. |
| plan: "Results committed to `tt-vga-capture/docs/results/`" | **not done** | flagged by the implementer; the controller's hardware run now supplies them, so this is a follow-up, not a defect in the code |

### The `--help` fix

The escaping approach is **complete and correct for this parser**, and the
"don't escape the epilog" decision is **right**:

* argparse's `HelpFormatter._format_text` interpolates a `description` or
  `epilog` only `if '%(prog)' in text`. Neither the demo's description nor
  its epilog contains one, so doubling per cents there would print them
  doubled. The comment at `demo.py:886` says exactly this.
* `for_help()` is applied to all five interpolated *values* and not to the
  `%(default)s` placeholders, which is the right side of the line.
* Crucially, the decision is not left resting on that argument:
  `test_every_subcommand_can_print_its_help` renders the **whole** help
  end-to-end, so a future epilog that gains a `%(prog)` alongside a literal
  per cent fails the test. `test_no_help_string_carries_an_unescaped_per_cent`
  then names the offending option. Together they close the hole properly.
* `uv run ttcap demo --help` confirmed working.

One residual: `for_help` is a `demo.py` export used by `demo.py` only. If
another subcommand later interpolates a path pattern, nothing points the
author at it except the test failing — acceptable, since the test *does*
fail.

### `--fps`

`parse_fps` (`demo.py:354`) accepts `30`, `30/1`, `29.97`; rejects `foo`,
`0`, `-30`, `30/0`, `1/2000` with sentences naming `--fps`. Verified:
`--fps 'foo' is not a frame rate: write 30, 30/1 or 29.97`. It lands on
`vgadecode` before the `tee`, so all four outputs share one cadence. Good.
Note the contrast with F7: `--fps` is validated against the element's own
range, `--seconds` and `--clock-hz` are not.

---

## Findings

### F1 — Important. A demo killed by anything but SIGINT orphans the board

`python/ttcap/demo.py:684` (`start_new_session=True`) with only SIGINT
handled at `demo.py:707`.

The new session is deliberate and buys the good single-Ctrl-C behaviour: the
child sees only the one forwarded signal. The cost is that the child sees
**nothing else** either. There is no `try/finally` that terminates it, no
`SIGTERM`/`SIGHUP` handler, and no `PR_SET_PDEATHSIG`.

Reproduced (`tmp/orphan_probe.py`): a `--no-png --seconds 0` run, SIGTERM to
the demo, then:

```
demo exit -15
t+1s ttcap alive=True
...
t+12s ttcap alive=True
ORPHANED: ttcap still capturing the board after the demo was killed
1793870 gst-launch-1.0 -e -m vgacapttsrc name=src link=serial:/dev/null ...
```

The detached `gst-launch` + `ttcap capture` pair ran until I `SIGKILL`ed it.
With `--seconds 0` it would run for ever. On the bench that means the next
person's run fails with "device busy" and no terminal owns the process.

Why it is not visible in the default configuration: with PNGs on,
`multifilesink post-messages=true` makes `gst-launch -m` write a bus line per
frame, so the moment the demo dies the child takes SIGPIPE on its next
message. That is luck, not a shutdown path — and `--no-png` removes it.
Closing the terminal (SIGHUP), `kill`, an OOM kill, or any unhandled
exception between `Popen` and the read loop all hit the same case.

**Fix:** keep `start_new_session=True`, and additionally (a) install the same
forwarding handler for `SIGTERM` and `SIGHUP`, and (b) wrap the read loop in
`try/finally` that `child.terminate()`s, then `child.kill()`s after
`stop-timeout`, on any exit path. A test for it is cheap — `tmp/orphan_probe.py`
in this worktree is one.

### F2 — Important. An outdir with old frames is overwritten silently, and the summary counts the strays

`demo.py:845` (`mkdir(parents=True, exist_ok=True)`) and `demo.py:645`
(`sorted(plan.outdir.glob("frame-*.png"))`).

Nothing checks whether the outdir already holds a previous run, and the
summary counts every `frame-*.png` in it rather than the files this run wrote.
The two together produce an actively false report. Verified:

```
# first run, 8 frames  -> 6 png(s), all six on disk
# second run into the SAME outdir, 2 frames -> wrote ZERO new files
capture finished after 0.3s (gst-launch exit 0)
  6 png(s) in tmp/rev/run1          <-- all six are the previous run's
```

(`ls -l --time-style=+%H:%M:%S` afterwards shows all six still stamped
`23:40:57`; only `capture.mkv` was rewritten. The identical capture into a
fresh directory honestly reports `0 png(s)`.)

This matters more than usual because this milestone's outputs are meant to be
committed under `docs/results/`: a short capture into a directory that held a
long one leaves a silently mixed set of frames, some of them from a different
design, and a summary that says the run succeeded.

**Fix:** refuse a non-empty outdir unless `--force`/`--overwrite` is given
(or move the old frames aside), and count the new files rather than globbing —
`multifilesink` posts one bus message per file, which `Progress.frames`
already counts, so `_summarise` can compare the two and say so when they
disagree.

### F3 — Important. The plugin not being on `GST_PLUGIN_PATH` produces no hint at all

`demo.py:763` checks only that `gst-launch-1.0` exists.

This is the single most likely setup failure for a freshly built plugin, and
it is the one failure the demo says nothing useful about:

```
writing tmp/rev/noplug/frame-%04d.png
writing tmp/rev/noplug/capture.mkv
<the pipeline>
WARNING: erroneous pipeline: no element "vgacapttsrc"

capture finished after 0.0s (gst-launch exit 1)
  0 png(s) in tmp/rev/noplug
  tmp/rev/noplug/capture.mkv was not written
```

Note also that the outdir is created before this is discovered, and that
"capture finished after 0.0s" describes a capture that never started.

The irony is that the code already has both the mechanism and the words:
`have_element()` (`demo.py:107`) is used for the encoder, and the
`gst-launch-1.0`-missing message at `demo.py:764` already says "make sure
`GST_PLUGIN_PATH` names the directory holding `libgstvgacap.so`".

**Fix:** in `plan_demo`, `have_element("vgacapttsrc")` and
`have_element("vgadecode")` next to the `gst-launch-1.0` check, raising that
same sentence. Two lines.

### F4 — Important. `--serve` bind failures name neither the flag nor the port

`demo.py:822` constructs `MjpegServer`, which binds in `mjpeg.py:208`; the
`OSError` reaches `cli.py`'s generic `_failed`.

```
$ ttcap demo ... --serve 8849          # 8849 held by another process
demo failed: OSError: [Errno 98] Address already in use

$ ttcap demo ... --serve 80
demo failed: PermissionError: [Errno 13] Permission denied
```

Neither says `--serve`, neither says which port, and the second does not say
that ports below 1024 need root. A user with `--outdir`, `--link` and
`--serve` on one line has three candidates for "permission denied". This is
the worst message in the command, because everything else the demo prints on
a bad argument is a full sentence.

**Fix:** catch `OSError` around the `MjpegServer(...)` construction and
re-raise as `CaptureError("--serve %d: %s -- pick another port (anything
above 1024 is free to use)" % (port, exc.strerror))`.

### F5 — Important. `--project`/`--design` conflicts and board-kind mismatches are only caught on the board

`demo.py:762` (`resolve_link`) and `demo.py:339-342` (both props appended
unconditionally).

Three cases, none caught by the demo:

* `--project p --design d` together: the demo builds
  `project=p design=d`, and the error arrives from the board as
  `capture failed: ValueError: project and design both name a tt.shuttle
  entry; give only one`, wrapped in two GStreamer `ERROR:` blocks. argparse's
  `add_mutually_exclusive_group()` is a three-line fix that turns it into a
  usage error before anything is contacted.
* `--design X --board tt07` (an ASIC slug): accepted, and fails on the board
  with a MicroPython traceback out of `select_project` (`capture.py:398`).
* `--project X --board fpga-1` (an FPGA slug): same.

`WELLAND[board]` already records which profile — and therefore which kind of
board — each slug is (`boards.py:151`, `fpga-*` → `RP2350_DBV3`). The demo
resolves the link through that table and then ignores the second half of the
tuple. One `if` gives "`--design` is for the FPGA boards (fpga-1..fpga-4);
tt07 is an ASIC, use `--project`".

Verified with `--dry-run`: all three print a pipeline and exit 0.

### F6 — Important. The tunnel hint's headline command needs root

`demo.py:216-238`, and the same example in `README.md` ("Reaching a Welland
board").

The hint is otherwise very good — it fires on the right failure, names the
gateway, and gives the follow-up `--link`. But its primary command uses the
board's address octet as the *local* port:

```
    ssh -N -L 7:10.21.2.7:8765 tweed.welland.mithis.com

then run the demo again against the near end of it:

    ttcap demo --link ws://127.0.0.1:7/serial ...

(a local port below 1024 needs root, so any free port does as well:
 ssh -N -L 18765:10.21.2.7:8765 tweed.welland.mithis.com, then --link ws://127.0.0.1:18765/serial)
```

Every Welland slug maps to an octet of 3–8 or 33–36, so *every* board's
headline command is a privileged port and fails for a normal user with
`Privileged ports can only be forwarded by root.` The working command is in
the parenthesis, which is the last thing read and the first thing skipped.
The controller's own successful hardware run used port 18733, not 7.

**Fix:** make the high port the headline (`18000 + octet`, or just
`18765`), and drop the parenthesis or invert it. Same in the README, whose
example is `ssh -N -L 7:10.21.2.7:8765 …`.

### F7 — Minor. `--seconds` and `--clock-hz` are not range-checked, unlike `--fps`

`demo.py:335` / `demo.py:912-920`.

```
$ ttcap demo ... --seconds -5
(gst-launch-1.0:1794653): GLib-GObject-CRITICAL **: value "-5.000000" of type
  'gdouble' is invalid or out of range for property 'seconds' of type 'gdouble'
```

…and the run then proceeds with `seconds` left at its default 0, i.e. it
captures until interrupted. A user who typed a bad duration gets an unbounded
capture plus a `CRITICAL` they will read as a crash. `--clock-hz 0` reaches
the element and produces the right sentence ("the clock-hz property is not
set; ttcap needs a project clock to program") but buried under two more
`ERROR:` blocks and "Failed to set pipeline to PAUSED", and it names the
property rather than the flag. `--clock-hz -1` is the same.

`parse_fps` refuses out-of-range values *precisely so* it is "a sentence
rather than a GObject warning from inside a running pipeline"
(`demo.py:382`). The same two lines are owed to `--seconds` (0..86400,
`gstvgacapttsrc.c:1245`) and `--clock-hz` (1..200000000,
`gstvgacapttsrc.c:1227`).

### F8 — Minor. `%g` turns a large `--seconds` into scientific notation

`demo.py:348-351`. `--seconds 1234567` prints and passes
`seconds=1.23457e+06` — lossy, and it weakens the "the printed pipeline is
the pipeline" claim. (It is out of the element's range anyway, so F7's check
would catch this one first.) `repr`-style formatting with a trailing `.0`
stripped, or `("%d" if value.is_integer() else "%r")`, avoids it.

### F9 — Minor. `--window` with no display says "writing a window" and exits 0

With `DISPLAY`/`WAYLAND_DISPLAY` unset, a `--window` run printed
`writing a window (autovideosink)`, produced six PNGs and a video, exited 0,
and no window ever existed. `autovideosink` fell back to a sink that does not
display. The implementer's known-wart note covers the *opposite* case (a
window failure taking the whole `tee` down); this is the quieter half. A
one-line check for `DISPLAY`/`WAYLAND_DISPLAY` before adding the branch,
saying "no display; dropping --window" (or refusing), would cover it.

### F10 — Minor. The summary describes outputs of a run that produced nothing

`demo.py:632-656`. On a failed run (no tunnel, missing serial device) the
summary still reads:

```
capture finished after 0.1s (gst-launch exit 1)
  0 png(s) in tmp/rev/ser
  tmp/rev/ser/capture.mkv, 0.0 KiB
```

"capture finished" and a 0.0 KiB file listed as an output. A non-zero
`returncode` should change the verb ("capture failed after …") and suppress
or annotate the zero-byte artefacts. Related: a *successful* run that wrote
zero PNGs also exits 0 with no comment.

### F11 — Minor. The exit-code contract in `cli.py` is now wrong

`cli.py:17-21` documents "0 success, 1 a board, link or tool error, 2 a usage
error, 3 a capture that produced no samples". `demo()` returns gst-launch's
own status straight through (`demo.py:859`): I observed **255** (preroll
failure), **130** (double Ctrl-C), and **1**. 3 in particular already means
something specific. Either map non-zero gst-launch statuses onto 1 or document
the exception in that docstring.

### F12 — Minor. `describe_timing` invents a polarity when the field is absent

`demo.py:565-566`: `"positive" if fields.get("hsync-positive") == "true" else
"negative"`. Every other field in that function falls back to `"?"`; these two
report `negative` for a message that did not carry the field at all. Cheap to
make `"?"`.

### F13 — Minor. fds leak if the MJPEG server cannot bind

`demo.py:819-826`. `os.pipe()` is created at `demo.py:779` inside a careful
`try/except BaseException` that closes both ends (`demo.py:800-805`), but
`MjpegServer(...)` is constructed *after* that block, so an `OSError` there
escapes with both descriptors open. Harmless (the process exits) but it is the
one gap in an otherwise deliberate cleanup path, and it sits right next to F4,
which is the fix's natural home.

### F14 — Minor. No hint when `fpgas-tt` has the serial port

`resolve_link` prints the right note up front *when it auto-detects the Pi*
(`demo.py:283-287`: "stop it first: `sudo systemctl stop fpgas-tt`"). But it
does not print it when the same device is reached with `--link
serial:/dev/ttboard`, and nothing repeats it when the capture fails with
`could not open port /dev/ttboard: [Errno 16] Device or resource busy`. The
bridge failure gets a hint on failure (`demo.py:722`); the serial-busy
failure, which is at least as common on the Pi, gets none. Symmetry would
help: on a non-zero exit with a `serial:/dev/ttboard` link, print the note.

(Not reproduced end-to-end — no board — but the path is clear from
`demo.py:722` being gated on `plan.link.through_bridge`.)

### F15 — Minor. `_address_is_local` can be fooled

`demo.py:199-205` binds a UDP socket to the board's bridge address and treats
success as "this is the Pi". On a host with `net.ipv4.ip_nonlocal_bind=1`
(routers, load balancers, some container hosts) that bind succeeds for any
address, so the demo would silently choose `serial:/dev/ttboard` on a
workstation. Comparing against `socket.getaddrinfo`/`ifaddrs` would be exact.
Low likelihood; noted because the hostname half of the test is itself an
unverified guess (the implementer's own concern #1: `WELLAND` records
`pi-sw2-p7` as a *power-switch port* name, and whether the Pi is named after
it is unconfirmed).

### F16 — Minor. `progress.say` inside the signal handler

`demo.py:694-699` prints from `on_interrupt`. A SIGINT delivered while the
main thread is inside `print` on the same stream can re-enter a locked
`io` buffer. Rare, and the payoff (telling the user to wait for the DMA
buffer) is worth something, but setting a flag and printing from the read
loop would be free of it.

### F17 — Minor. Test gaps

The suite is good and the `--help` hole is now properly closed, but the
following paths have no coverage, and four of them are findings above:

| path | finding |
|---|---|
| SIGTERM/SIGHUP at the demo (orphan) | F1 |
| an outdir that already holds frames | F2 |
| `vgacapttsrc` missing from the registry | F3 |
| `--serve` on a taken or privileged port | F4 |
| `--project` and `--design` together | F5 |
| a second SIGINT | — (behaviour verified good below; worth pinning) |
| a viewer disconnecting mid-stream (the `BrokenPipeError` arm of `mjpeg.py:191`) | — |
| two HTTP viewers at once (the broadcaster fan-out is tested, the *server* fan-out is not) | — |
| `--seconds`/`--clock-hz` out of range | F7 |

Also: `test_an_encoder_that_is_not_installed_is_named` is the suite's one skip
and skips on any machine with both encoders — i.e. almost always. It can be
made deterministic by monkeypatching `demo.have_element`, which would exercise
one of the command's best messages on every run rather than never.
(I exercised it by hand via `GST_PLUGIN_SYSTEM_PATH`; both branches are
correct.)

---

## What a new user hits

Every message below was provoked in this worktree. "Helps?" is whether the
message alone tells the user what to do next.

| situation | what the user sees | helps? |
|---|---|---|
| `--board tt9` | `demo failed: CaptureError: unknown board 'tt9': --board takes one of fpga-1, … tt08. A board that is not on the Welland bench is reached with --link instead, e.g. --link serial:/dev/ttyACM0.` | **yes** — the model answer |
| neither `--board` nor `--link` | `no board: pass --board (one of …) or --link serial:/dev/ttyACM0 or --link ws://host:8765/serial` | **yes** |
| `--no-png --no-video`, nothing else | `nothing to write: --no-png and --no-video with no --window and no --serve leaves the capture with nowhere to go` | **yes** |
| no encoder installed | `no video encoder: none of x264enc, vp8enc is installed. Install gst-plugins-good (vp8enc) or gst-plugins-ugly (x264enc), or pass --no-video.` | **yes** |
| `--video-encoder x264enc`, not installed | `--video-encoder x264enc but GStreamer has no x264enc element; the others the demo knows are vp8enc` | **yes** |
| `--fps foo` / `--fps 0` / `--fps 1/2000` | `--fps 'foo' is not a frame rate: write 30, 30/1 or 29.97` / `must be positive` / `outside vgadecode's 1/1000 to 1000/1 range` | **yes** |
| no tunnel to the bench | the GStreamer error (`the capture failed (exit status 1): capture failed: TimeoutError: timed out`) + `argv:` line + `Internal data stream error`, then the summary, **then the full tunnel hint** | **mostly** — the hint is right and prominent, but its headline `ssh -N -L 7:…` needs root (F6), and the last GStreamer line before the summary is the useless "Internal data stream error" |
| serial device missing | `the capture failed (exit status 1): capture failed: SerialException: [Errno 2] could not open port /dev/ttyNOPE` then `Internal data stream error` | **mostly** — the real cause survives, eight lines above the noise |
| board busy (`fpgas-tt` holding `/dev/ttboard`) | the same shape, `[Errno 16] Device or resource busy`, and **no** `systemctl stop fpgas-tt` hint even though the demo prints that note elsewhere | **no** (F14) |
| plugin not on `GST_PLUGIN_PATH` | `WARNING: erroneous pipeline: no element "vgacapttsrc"` then `capture finished after 0.0s` | **no — the worst one** (F3) |
| `--serve` port in use | `demo failed: OSError: [Errno 98] Address already in use` | **no** (F4) |
| `--serve 80` | `demo failed: PermissionError: [Errno 13] Permission denied` | **no** (F4) |
| `--outdir` is an existing file | `demo failed: FileExistsError: [Errno 17] File exists: 'tmp/rev/afile'` | **partly** — names the path, not the flag |
| `--outdir` unwritable | `demo failed: PermissionError: [Errno 13] Permission denied: 'tmp/rev/ro/sub'` | **partly** |
| `--outdir` full of old frames | nothing at all; frames silently blended, summary counts the strays | **no** (F2) |
| `--seconds -5` | `GLib-GObject-CRITICAL **: value "-5.000000" … is invalid or out of range`, then an unbounded capture | **no** (F7) |
| `--clock-hz 0` | `the clock-hz property is not set; ttcap needs a project clock to program` buried under `pipeline doesn't want to preroll` / `Failed to set pipeline to PAUSED` | **partly** (F7) |
| `--project` and `--design` together | accepted; fails on the board | **no** (F5) |
| `--design` on `tt07`, `--project` on `fpga-1` | accepted; fails on the board | **no** (F5) |
| `--window` with no display | `writing a window (autovideosink)`, exit 0, no window | **no** (F9) |
| Ctrl-C | `interrupted: asking the pipeline to end the stream. The board needs one DMA buffer to wind down, so give it a moment.` | **yes** — names the wait and why |
| Ctrl-C twice | `interrupted again: stopping now` | **yes** |

---

## Things I checked and found correct

### `--dry-run` really is inert

`--board tt07 --serve 8848 --window --dry-run`: the outdir did **not** exist
afterwards, port 8848 was still bindable, exit 0, and the pipeline went to
stdout while everything else the command says goes to stderr. `DRY_RUN_MJPEG_FD`
(`demo.py:748`) shows `fd=3` without opening a pipe. This is exactly right.

### The MJPEG server

Probed with `tmp/serve_probe.py` against a live `--serve` run:

* **Loopback only.** `ss -ltnp` → `LISTEN 0 5 127.0.0.1:8851 0.0.0.0:*`.
  Bound explicitly at `mjpeg.py:206` with a documented reason. Correct for
  something that exposes a live lab board.
* **A second browser works.** Two concurrent `/stream.mjpg` clients both got
  `multipart/x-mixed-replace; boundary=vgacapframe` and both received JPEG
  data.
* **A viewer disconnecting does not kill the capture.** Viewer A's socket was
  closed hard (`SO_LINGER 1,0`); viewer B kept receiving and the demo stayed
  alive. The `BrokenPipeError`/`ConnectionResetError` arm plus `unsubscribe`
  in a `finally` (`mjpeg.py:191-194`) is doing its job.
* **No thread or socket leak.** Before: `threads=4 fds=8`. After ten more
  viewers connected and dropped: `threads=4 fds=8`, unchanged.
* 404s are handled (`no such thing here`); the index and the stream are the
  only two routes; HTTP/1.0 with `Connection: close` avoids keep-alive
  confusion; the back-pressure design (depth 4, drop oldest) is right for a
  live capture and is tested.
* `MjpegServer.close()`'s `_started` flag (`mjpeg.py:214`) is a real bug the
  implementer found and fixed — `shutdown()` on a never-entered
  `serve_forever` hangs for ever.

### Ctrl-C

Probed with `tmp/signal_probe.py`, watching the `ttcap` grandchild's pid:

| | demo exit | grandchild after exit | `capture.mkv` |
|---|---|---|---|
| one SIGINT | 0 | **dead** (wound down) | `Duration: 0:00:00.319200000`, 97.5 KiB |
| two SIGINTs, 0.4 s apart | 130 | **dead** | `Duration: 0:00:00.336000000`, 105.9 KiB |

So: the signal does reach the child, the board does wind down through
`vgacapttsrc`'s cooperative stop, the video is finalised, and **a second
Ctrl-C does not leave the board capturing** — it is in fact gentler than the
implementer's own warning suggests, since the Matroska file survived that too.
The `128 - returncode` mapping at `demo.py:859` correctly turns `-2` into 130.

The only hole is F1: this is all specific to SIGINT.

### Other

* No `uri=` is built anywhere; `ttcap-command` travels only as an element
  property, and the reasoning is documented at the top of `demo.py` and in the
  README. The allow-list threat model is respected.
* The printed pipeline round-trips: an `--outdir` containing a space
  (`tmp/rev/has space`) produced six PNGs and a 48.7 KiB video, and
  `_join`'s decision to leave bare `!` separators while quoting everything
  else (`demo.py:525`) is both readable and correct — `gst_parse_launchv`
  escapes argv tokens itself, so a multi-word `ttcap-command` survives.
* `line_buffered` (`demo.py:615`) and its explanation of why `stdbuf -oL` is
  deliberately *not* part of `DemoPlan.argv` is the kind of note that saves the
  next reader twenty minutes.
* Ordering in `plan_demo` — board slug checked before `gst-launch-1.0` is
  looked for — is the right call and is commented as such.
* Prose throughout is unusually good: the docstrings explain *why*, not what,
  and the README section is accurate apart from the port-7 example.

---

## Verdicts

* **Spec compliance: PASS.** Every item in the plan's Task 5 and in the
  controller's dispatch is implemented, and the two I could verify most
  sceptically — `--dry-run` touching nothing, and the source never going
  through a URI — hold up. The plan's "results committed to
  `tt-vga-capture/docs/results/`" is the only unmet line, and it needs the
  controller's hardware outputs rather than more code.

* **Quality: CHANGES REQUESTED.** The happy path is proven on hardware and
  the internals are careful — the MJPEG server in particular is better than
  it needed to be, and Ctrl-C is genuinely solid. But this is the milestone's
  user-facing deliverable, and six of the failures a user will actually hit
  are handled worse than the ones that are handled beautifully: an orphaned
  capture holding a bench board after the terminal closes (F1), a summary
  that reports a previous run's frames as this run's (F2), and no hint at all
  for the commonest setup mistake (F3) are the three I would not ship. F4–F6
  are each a two-to-five-line fix and would lift the whole command to the
  standard the board-slug and encoder messages already set.

**Counts:** 0 critical, 6 important (F1–F6), 11 minor (F7–F17).
