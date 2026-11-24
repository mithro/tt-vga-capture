# SPDX-License-Identifier: Apache-2.0
"""Hardware test of vgacap's RTL framer on a Tiny Tapeout FPGA board.

The board runs tt-vga-testpatterns' tt_um_vgacal_framer: the bars picture,
sampled every other clock, through vgacap_raw_framer; uo_out carries the
framer's chunk bytes and uio[0] marks the clocks that carry one. On the
RP2350 demo board uio[0..7] are GPIO 25..32 and uo_out[0..7] GPIO 33..40,
so one 16-pin `in pins` from GPIO 25 sees both: ttcap's ordinary streaming
capture with a 16-bit profile, phase-locked to the project clock.

Two checks:

  logic  At a clock the link carries losslessly (default 250 kHz, 500 KB/s
         of 16-bit samples): more than a whole frame, no overruns. The valid
         bytes, parsed as vgacap chunks, must be RAW chunks only (no
         framer overrun TIME chunk) whose samples are the bars picture on
         every other clock, all the way through.
  speed  At the design's real 25 MHz, which no serial link carries (and
         which ttcap's streaming script, rated to ~750 kHz, cannot run at:
         it sent nothing at all): a one-shot window instead, BOARD_WINDOW
         below. The same sampler fills up to 32K words of RAM by DMA --
         65,536 consecutive clocks, ~2.6 ms; halved while the heap has no
         block that big, down to 8K -- and the board prints them as base64.
         Every framer chunk in the window must decode to bars samples, and
         consecutive chunks must sit exactly 512 clocks apart in the picture.

    cd vgacap/python && uv run python <this file> ws://127.0.0.1:18035/serial OUTDIR

The bitstream must already be loaded (tt-vga-testpatterns tools/upload.py).
Exit 0 when both checks pass.
"""
from __future__ import annotations

import argparse
import dataclasses
import pathlib
import struct
import sys

import numpy as np
from ttcap.boards import RP2350_DBV3
from ttcap.capture import CaptureRequest, run_capture, select_project, stop_clock
from ttcap.cli import link_from_url
from ttcap.repl import RawRepl
from vgacap.stream import read_chunks

H_TOTAL, V_TOTAL = 800, 525
FRAME = H_TOTAL * V_TOTAL
FRAMER_SAMPLES = 256  # vgacap_raw_framer's samples_per_chunk
FRAMER_CHUNK = 8 + 4 + FRAMER_SAMPLES  # tag, length, sample_count, samples

#: uio[0] (GPIO 25) .. uo_out[7] (GPIO 40); bit 0 = valid, bits 15:8 = byte.
PROFILE = dataclasses.replace(
    RP2350_DBV3,
    name="rp2350-dbv3-uio0-uo16",
    uo_gpios=tuple(range(25, 41)),
    in_base=25,
    in_count=16,
    sample_bits=16,
    samples_per_word=2,
)


def bars_frame() -> list[int]:
    """tt_um_vgacal_bars' uo_out for one frame; sample k at (k % 800, k // 800).

    The same timing as hvsync_generator.v and the design's cocotb test:
    hsync low for h 656..751, vsync low on lines 490..491 (advanced to the
    next line from h 656), colour (h // 10) & 63 inside 640x480.
    """
    out = []
    for v in range(V_TOTAL):
        for h in range(H_TOTAL):
            hs = 0 if 656 <= h < 752 else 1
            vline = v if h < 656 else (v + 1) % V_TOTAL
            vs = 0 if 490 <= vline < 492 else 1
            c = (h // 10) & 63 if (h < 640 and v < 480) else 0
            out.append((hs << 7) | ((c & 1) << 6) | (((c >> 2) & 1) << 5) | (((c >> 4) & 1) << 4)
                       | (vs << 3) | (((c >> 1) & 1) << 2) | (((c >> 3) & 1) << 1) | ((c >> 5) & 1))
    return out


def board_windows(data: bytes) -> tuple[list[list[int]], list[str]]:
    """The 16-bit samples of each board RAW chunk, and the TIME messages."""
    windows, messages = [], []
    for tag, payload in read_chunks(data):
        if tag == "RAW ":
            count = struct.unpack_from("<I", payload, 0)[0]
            s = []
            for (w,) in struct.iter_unpack("<I", payload[4:]):
                s += [(w >> 16) & 0xFFFF, w & 0xFFFF]  # first sample in the high half
            windows.append(s[:count])
        elif tag == "TIME":
            messages.append(payload[18:].decode("utf-8", "replace"))
    return windows, messages


def valid_bytes(samples: list[int]) -> bytes:
    return bytes((s >> 8) & 0xFF for s in samples if s & 1)


def framer_chunks(data: bytes, pos: int = 0):
    """(tag, payload) of the framer's chunks from `pos`; stops at a partial one."""
    while pos + 8 <= len(data):
        tag = data[pos:pos + 4]
        (length,) = struct.unpack_from("<I", data, pos + 4)
        if pos + 8 + length > len(data):
            return
        yield tag, data[pos + 8:pos + 8 + length]
        pos += 8 + length


def raw_samples(payload: bytes) -> list[int]:
    (count,) = struct.unpack_from("<I", payload, 0)
    if count != FRAMER_SAMPLES or len(payload) != 4 + count:
        raise AssertionError("framer RAW chunk of %d samples, %d bytes" % (count, len(payload)))
    out = []
    for (w,) in struct.iter_unpack("<I", payload[4:]):
        out += [(w >> 24) & 255, (w >> 16) & 255, (w >> 8) & 255, w & 255]
    return out


def phases(samples: list[int], frame):
    """Every k0 with samples[i] == frame[(k0 + 2 i) % FRAME] for all i.

    Usually one; several when the samples lie in vertical blanking, which is
    the same black line with the same hsync line after line. `frame` is a
    numpy array; the candidates are narrowed sample by sample.
    """
    cand = np.arange(FRAME)
    for i, s in enumerate(samples):
        cand = cand[frame[(cand + 2 * i) % FRAME] == s]
        if cand.size == 0:
            break
    return cand


def phase(samples: list[int], frame) -> int | None:
    """The first k0 that fits (see phases()), or None."""
    cand = phases(samples, frame)
    return int(cand[0]) if cand.size else None


def capture(link_url: str, clock_hz: int, max_bytes: int, seconds: float, out: pathlib.Path):
    link = link_from_url(link_url)
    try:
        repl = RawRepl(link)
        repl.enter()
        try:
            req = CaptureRequest(profile=PROFILE, project=None, design=None, clock_hz=clock_hz,
                                 seconds=seconds, max_bytes=max_bytes, edge="falling",
                                 desc="tt_um_vgacal_framer uio[0]+uo_out at %d Hz" % clock_hz)
            # Starts the project clock at clock_hz, as `ttcap capture` does.
            # Without it the run relied on a clock someone else had left
            # running, and the one after a stop_clock() waited for edges
            # that never came ("board went quiet").
            select_project(repl, req)
            with out.open("wb") as fp:
                stats = run_capture(repl, req, fp)
            stop_clock(repl)
        finally:
            repl.exit()
    finally:
        link.close()
    return stats


def check_logic(data: bytes, frame: list[int], log) -> bool:
    windows, messages = board_windows(data)
    samples = [s for w in windows for s in w]
    log("logic: %d board chunks, %d clocks, TIME %s" % (len(windows), len(samples), messages))
    stream = valid_bytes(samples)
    first = stream.find(b"RAW ")
    if first < 0:
        log("logic: FAIL, no framer RAW chunk in %d valid bytes" % len(stream))
        return False
    framed, other = [], []
    for tag, payload in framer_chunks(stream, first):
        if tag == b"RAW ":
            framed += raw_samples(payload)
        else:
            other.append((tag, payload[:24]))
    log("logic: %d valid bytes, framer stream from byte %d: %d samples, other chunks %s"
        % (len(stream), first, len(framed), other))
    k0 = phase(framed, frame)
    ok = not other and k0 is not None and len(framed) > FRAME // 2
    log("logic: %s, %d framer samples (%.2f frames of every-other-clock samples) are the bars "
        "picture from frame offset %s" % ("PASS" if ok else "FAIL", len(framed),
                                          2 * len(framed) / FRAME, k0))
    return ok


#: The one-shot board program for the speed check. Pins and PIO handling as
#: ttcap's prelude does them (see its CLK_WAIT_GPIO and set_gpio_base notes):
#: PIO1's window moved to GPIO 16, absolute pin numbers throughout.
BOARD_WINDOW = """
import rp2, machine, gc, time, ubinascii
from machine import Pin
buf = None  # an earlier run's buffer, still in the REPL's globals
gc.collect()
WORDS = %(words)d
tt.clock_project_PWM(%(hz)d)
p = rp2.PIO(1)
try:
    p.remove_program()
except Exception:
    pass
p.gpio_base(16)
for n in range(25, 41):
    Pin(n, Pin.IN)
@rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_LEFT, autopush=True, push_thresh=32, fifo_join=rp2.PIO.JOIN_RX)
def samp():
    wrap_target()
    wait(1, gpio, 16)
    wait(0, gpio, 16)
    in_(pins, 16)
    wrap()
sm = rp2.StateMachine(4, samp, in_base=Pin(25))
gc.collect()
buf = None
while WORDS >= 4096:
    try:
        buf = bytearray(WORDS * 4)
        break
    except MemoryError:
        WORDS //= 2
        gc.collect()
d = rp2.DMA()
machine.mem32[0x50300008] = 0xFFF  # clear FDEBUG sticky flags
d.config(read=0x50300020, write=buf, count=WORDS,
         ctrl=d.pack_ctrl(size=2, inc_read=False, inc_write=True, treq_sel=12), trigger=True)
sm.active(1)
t0 = time.ticks_ms()
while d.active() and time.ticks_diff(time.ticks_ms(), t0) < 2000:
    pass
sm.active(0)
print("INFO words=%%d base=%%s sysclk=%%d dma_active=%%d rxstall=%%d" %% (WORDS, p.gpio_base(), machine.freq(), d.active(), machine.mem32[0x50300008] & 1))
d.close()
p.remove_program()
for i in range(0, len(buf), 3072):
    print("D" + ubinascii.b2a_base64(buf[i:i + 3072]).decode().strip())
print("END")
"""


def capture_window(link_url: str, hz: int, words: int, out: pathlib.Path, log) -> list[int]:
    import base64
    link = link_from_url(link_url)
    try:
        repl = RawRepl(link)
        repl.enter()
        try:
            stdout, stderr = repl.exec(BOARD_WINDOW % {"words": words, "hz": hz}, timeout=180)
            stop_clock(repl)
        finally:
            repl.exit()
    finally:
        link.close()
    out.with_suffix(".stdout.txt").write_text(stdout)
    if stderr.strip():
        raise RuntimeError("board: " + stderr.strip())
    lines = stdout.split()
    info = [ln for ln in stdout.splitlines() if ln.startswith("INFO")]
    log("speed: board %s" % info)
    # Not rxstall: the state machine keeps sampling after the DMA's count is
    # reached, so its 8-word FIFO fills (in under a microsecond) and stalls
    # before the polling loop can stop it -- always 1, and after the window.
    # A sample lost *inside* the window shows in check_speed's chunk steps.
    if "END" not in lines or not info or "dma_active=0" not in info[0]:
        raise RuntimeError("speed: window incomplete: %s" % info)
    # Data lines only: the SDK logs to stdout too ("Clocking at ...Hz").
    raw = b"".join(base64.b64decode(ln.strip()[1:]) for ln in stdout.splitlines()
                   if ln.startswith("D"))
    got = int(info[0].split("words=")[1].split()[0])
    if len(raw) != 4 * got or got < 8192:
        raise RuntimeError("speed: %d bytes decoded for %d words" % (len(raw), got))
    out.write_bytes(raw)
    samples = []
    for (w,) in struct.iter_unpack("<I", raw):
        samples += [(w >> 16) & 0xFFFF, w & 0xFFFF]
    return samples


def check_speed(samples: list[int], frame, log) -> bool:
    stream = valid_bytes(samples)
    log("speed: %d clocks, %d valid bytes (%.3f a clock)" % (len(samples), len(stream),
                                                            len(stream) / len(samples)))
    first = stream.find(b"RAW ")
    good, bad, other = 0, 0, []
    # The offsets still consistent with every chunk so far, each chunk
    # 2 * FRAMER_SAMPLES clocks after the one before: empty means a sample
    # was lost or repeated somewhere in the window.
    chain = None
    for tag, payload in framer_chunks(stream, first if first >= 0 else len(stream)):
        if tag != b"RAW ":
            other.append(tag)
            continue
        cand = phases(raw_samples(payload), frame)
        if cand.size == 0:
            bad += 1
            continue
        good += 1
        if chain is None:
            chain = cand
        else:
            chain = np.intersect1d((chain + 2 * FRAMER_SAMPLES) % FRAME, cand)
    contiguous = chain is not None and chain.size > 0
    ok = good > 10 and bad == 0 and not other and contiguous
    log("speed: %s, %d framer chunks are bars samples, %d are not, other chunks %s; "
        "all of them one contiguous run %d clocks apart: %s (last chunk at frame offset %s)"
        % ("PASS" if ok else "FAIL", good, bad, other, 2 * FRAMER_SAMPLES, contiguous,
           [int(k) for k in chain[:3]] if contiguous else None))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("link")
    ap.add_argument("outdir", type=pathlib.Path)
    ap.add_argument("--logic-hz", type=int, default=250_000)
    ap.add_argument("--speed-hz", type=int, default=25_000_000)
    ap.add_argument("--only", choices=("logic", "speed"))
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    logf = (args.outdir / "hil_framer.log").open("a")

    def log(msg: str) -> None:
        print(msg, flush=True)
        logf.write(msg + "\n")
        logf.flush()

    frame = np.array(bars_frame(), dtype=np.uint8)
    results = []
    if args.only in (None, "logic"):
        # 1.1 frames of clocks at 2 bytes a sample, plus chunk overhead.
        path = args.outdir / "logic.vgacap"
        stats = capture(args.link, args.logic_hz, int(FRAME * 1.1) * 2 + 65536, 0, path)
        log("logic capture at %d Hz: %s" % (args.logic_hz, stats))
        results.append(stats.overruns == 0 and stats.rxstall == 0
                       and check_logic(path.read_bytes(), frame, log))
    if args.only in (None, "speed"):
        samples = capture_window(args.link, args.speed_hz, 32768,
                                 args.outdir / "speed_window.bin", log)
        results.append(check_speed(samples, frame, log))
    log("RESULT %s" % ("PASS" if all(results) else "FAIL"))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
