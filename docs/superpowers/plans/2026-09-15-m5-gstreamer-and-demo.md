# Milestone 5: GStreamer plugin and the demo — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GStreamer plugin that turns a `vgacap` stream into `video/x-raw` frames (`vgadecode`), a source element that runs a capture on a Tiny Tapeout board (`vgacapttsrc`), a convenience bin (`vgacapbin`), and a demo driver that captures a Welland board and produces PNGs, an MKV, a local window and a browser-viewable stream.

**Architecture:** `vgadecode` is a C `GstBaseTransform`-style element wrapping `libvgaframe`: bytes in (`application/x-vgacap`), RGB frames out, with `repeat-last-frame` to present a steady rate. `vgacapttsrc` is a C `GstPushSrc` that spawns the Python capture flow as a subprocess (`ttcap capture --out -` streaming to stdout) and pushes its bytes; this keeps the board protocol in one place (Python) and the plugin small, and lets the same source later run `ttcap` over the bridge or serial. `vgacapbin` links a source chosen by URI scheme to `vgadecode`. Two `libvgaframe` robustness fixes found on hardware come first (glitch-tolerant line starts; retroactive first frame). The Python side gains a streaming API (`iter_capture`/`CaptureSession`) so `ttcap capture --out -` and future elements share one implementation.

**Tech Stack:** GStreamer 1.x (`gstreamer-1.0`, `gstreamer-base-1.0`, `gstreamer-video-1.0`; dev headers installed on the workstation and available on the Pis' Raspbian bookworm via apt), CMake (pkg-config), C99, Python via `uv`, `gst-launch-1.0`, `hlssink2`/`multipartmux` + a tiny HTTP server for the browser view.

**Spec:** `docs/superpowers/specs/2026-09-15-tt-vga-capture-design.md` §5.2, §5.6, §5.7, §7, §8. Inputs: `docs/research/2026-09-15-micropython-capture-rate.md` (clock ceilings), the M3 final review's M5/M6 recommendations (`vgacap/.superpowers/sdd/2026-09-15-m3-micropython-capture/final-review.md`, archived copy under `docs/reviews/` once M3 closes).

## Global Constraints

- Apache-2.0; SPDX headers; C99 for the plugin; no allocation after init inside `libvgaframe` (the element allocates its buffers once in `start()`).
- Element names and caps: `vgadecode` sink caps `application/x-vgacap`, src caps `video/x-raw, format=RGB, width=[1,4096], height=[1,4096], framerate=[0/1,120/1]`; `vgacapttsrc` src caps `application/x-vgacap`; the bin exposes `vgadecode`'s src pad.
- Frame rate: `vgadecode` timestamps frames from the stream's nominal `clock_hz` and the detected clocks per frame (project time), and optionally re-times to wall clock with `repeat-last-frame=true` at a fixed `output-fps`.
- Python via `uv` only; the Pi runs with `UV_NO_DEV=1`; `ttcap capture --out -` writes the stream to stdout with nothing else on stdout (all messages to stderr).
- Hardware runs (Welland boards) are done by the controller; sub-agents deliver code plus host tests with fakes.

## File structure

```
vgacap/
  src/frame/timing.c, frame.c        (Task 1 fixes)
  gst/CMakeLists.txt                 plugin build (pkg-config; optional target, off when GStreamer is absent)
  gst/gstvgacap.c                    plugin_init registering the three elements
  gst/gstvgadecode.[ch]              GstBaseTransform subclass around vgacap_reader + vgaframe
  gst/gstvgacapttsrc.[ch]            GstPushSrc subclass running `ttcap capture --out -` as a child process
  gst/gstvgacapbin.[ch]              GstBin: source by URI scheme + vgadecode
  gst/tests/test_plugin.py           gst-inspect + file-to-PNG pipeline tests (pytest, needs gst-python or gst-launch)
  python/ttcap/capture.py            iter_capture(), CaptureSession, stream_header_bytes(), --out -
  python/ttcap/demo.py               `ttcap demo`: select board/project, capture, run pipelines
tt-vga-capture/docs/results/...      demo outputs
```

## Tasks

### Task 1: `libvgaframe` robustness (C)
- Glitch tolerance: once the learner has a `hsync_width` and `clocks_per_line` (after the first full line pair), only accept a line start whose pulse width is within 25% of the learned width and whose distance from the previous accepted line start is at least 50% of `clocks_per_line`; other pulses are ignored and counted in a new `timing.glitches` field. Test: the synthetic 640x480 stream with injected 2-30 clock hsync pulses (a few per frame) still yields complete frames; the tt08 Tiny Logo capture (`tt-vga-capture/tmp/tt08_tt_um_rejunity_vga_logo.vgacap`, committed gzipped as a test fixture under `tests/fixtures/` if under 1 MB, else regenerated synthetically) reconstructs.
- Retroactive first frame: when the first short vsync phase completes (both levels seen once), treat the pulse's leading edge, which is `vsync_lines` lines back, as the frame start: set `y = vsync_lines` (lines already elapsed since the pulse) and `in_frame = 1` so the frame between the first and second pulses is emitted. Test: two full frames of synthetic samples starting mid-frame yield one complete frame (previously zero).
- Both behaviours documented in `frame.h`; `vgacap-frames` prints `glitches=N`.

### Task 2: streaming capture API (Python)
- `iter_capture(repl, req) -> Iterator[bytes]` yielding the VGCH header first, then each chunk verbatim; `CaptureSession` with `.chunks()`, `.stats()`, `.request_stop()`, `.close()` (close = recovery path); `run_capture` becomes a thin wrapper writing to a file; `CaptureRequest` accepts `seconds=0, max_bytes=0` when a `stop` callable is provided; `ttcap capture --out -` streams to stdout (binary, unbuffered) and puts all messages on stderr; a `RawRepl` write lock so `request_stop()` from another thread is safe. FRAM chunks are counted like RAW (samples from the header) so M6 streams do not report zero samples. Tests with the fake boards.

### Task 3: `vgadecode`
- C element wrapping `vgacap_reader` + `vgaframe`; properties `repeat-last-frame` (bool), `output-fps` (fraction, default 30/1), `max-width`, `max-height`, `force-mode` (string, table name), `partial` (bool: also push partial frames); metadata in the buffer (frame counter, partial flag) via a `GstMeta` or a bus message; caps renegotiated when the detected size changes; timestamps from project clock when `clock_hz` is known. Tests: `gst-launch-1.0 filesrc location=... ! vgadecode ! pngenc ! multifilesink` over the synthetic streams and the committed hardware captures; frames pixel-equal to `vgacap-frames` output.

### Task 4: `vgacapttsrc` and `vgacapbin`
- `vgacapttsrc` properties: `link` (`serial:/dev/ttboard` or `ws://...`), `project`, `design`, `clock-hz`, `profile`, `pio`, `buf-words`, `seconds`; runs `uv run --no-sync ttcap capture --out - ...` (configurable `ttcap-command`) with stdout piped; pushes 64 KiB buffers; stops the child cooperatively on `stop()` (SIGINT then wait); reports the child's stderr summary on the bus. `vgacapbin` parses `uri` (`tt-serial:///dev/ttboard?project=...&clock=...`, `tt-ws://host:8765/serial?...`, `file:///path`) into the right source plus `vgadecode`, exposes the video src pad and forwards properties. Tests with a fake `ttcap` script that emits a synthetic stream.

### Task 5: `ttcap demo` and the browser view (controller runs hardware)
- `ttcap demo --board tt07 --project tt_um_rejunity_vga --clock-hz 60000 --seconds 60 --outdir DIR [--window] [--serve PORT]`: selects the Welland Pi/link from `WELLAND`, runs the capture through `vgacapbin`, writes `frame-%04d.png` (`pngenc ! multifilesink`), `capture.mkv` (`x264enc` or `vp8enc` fallback, `matroskamux`), optionally `autovideosink`, optionally an MJPEG `multipart/x-mixed-replace` HTTP endpoint (`jpegenc ! multipartmux` piped to a tiny Python HTTP server) viewable in a browser. Results committed to `tt-vga-capture/docs/results/`.

### Task 6: CI and HIL
- CI builds the plugin when GStreamer is present (ubuntu-latest has it via apt in the workflow) and runs the file-to-PNG test. A `tools/hil.sh` in `vgacap` documents the hardware-in-the-loop run the controller performs on a Welland Pi (12-item list from the M3 final review), producing a short report file that is committed under `docs/results/`.
