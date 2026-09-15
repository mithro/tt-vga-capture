# SPDX-License-Identifier: Apache-2.0
"""Exploration: run vgacap's MicroPython capture script on a Welland board
through the debug bridge and read its chunks length-driven.

    uv run --project ../vgacap python tools/tt_capture_smoke.py \
        ws://127.0.0.1:18733/serial --profile rp2350 --design tt_um_vga_pattern \
        --clock-hz 500000 --seconds 8 --out tmp/smoke.vgacap

Writes a vgacap stream (host-written VGCH header + the board's RAW/TIME
chunks). Debug path only (bridge); the real capture flow is `ttcap capture`.
"""
from __future__ import annotations

import argparse
import struct
import sys
import time

from ttcap.boards import RP2040_TT06, RP2350_DBV3
from ttcap.capture import capture_cfg
from ttcap.mp import load, with_cfg
from ttcap.repl import RawRepl, WebSocketLink
from vgacap.stream import Header, Writer

KNOWN = {b"VGCH", b"RAW ", b"RLE ", b"FRAM", b"EVNT", b"TIME"}


def read_exact(link: WebSocketLink, buf: bytearray, n: int, timeout: float) -> bytes:
    t0 = time.time()
    while len(buf) < n:
        chunk = link.read(0.5)
        if chunk:
            buf += chunk
        elif time.time() - t0 > timeout:
            raise TimeoutError(f"wanted {n} bytes, have {len(buf)}")
    out = bytes(buf[:n])
    del buf[:n]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--profile", choices=["rp2040", "rp2350"], required=True)
    ap.add_argument("--design", help="tt.shuttle entry to enable")
    ap.add_argument("--clock-hz", type=int, default=500000)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--buf-words", type=int, default=2048)
    ap.add_argument("--pio", type=int, default=0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    profile = RP2040_TT06 if a.profile == "rp2040" else RP2350_DBV3

    link = WebSocketLink(a.url)
    repl = RawRepl(link)
    repl.enter()
    try:
        if a.design:
            out, err = repl.exec(f"tt.shuttle['{a.design}'].enable()")
            print("enable:", out.strip(), err.strip())
        for code in ["tt.clock_project_stop()", "tt.reset_project(True)",
                     f"print(tt.clock_project_PWM({a.clock_hz}))", "tt.reset_project(False)"]:
            out, err = repl.exec(code)
            print(f"{code}: {out.strip()} {err.strip()}")
        cfg = capture_cfg(profile, buf_words=a.buf_words, max_bytes=0, edge="falling")
        cfg["pio"] = a.pio
        print("cfg:", cfg)
        script = with_cfg(load("capture_rp2.py"), cfg)
        # Hardware finding 2026-09-15: the firmware already sets PIO1/PIO2's
        # gpio_base to 16 and the sdk refuses to set it again while the block
        # holds a program; only set it when it differs.
        guarded = (
            "        _want = GPIO_BASE\n"
            "        _have = str(rp2.PIO(PIO_NUM).gpio_base())\n"
            "        if not _have.startswith('Pin(GPIO%d,' % _want):\n"
            "            rp2.PIO(PIO_NUM).gpio_base(_want)\n"
        )
        assert "        rp2.PIO(PIO_NUM).gpio_base(GPIO_BASE)\n" in script
        script = script.replace("        rp2.PIO(PIO_NUM).gpio_base(GPIO_BASE)\n", guarded)
        # Hardware finding 2026-09-15: machine.Pin(clk, Pin.IN) switches the
        # clock pad away from its PWM function and kills the project clock.
        assert "init_input_pins(machine.Pin, CLK_GPIO, IN_BASE, IN_COUNT)" in script
        script = script.replace("init_input_pins(machine.Pin, CLK_GPIO, IN_BASE, IN_COUNT)",
                                "init_input_pins(machine.Pin, IN_BASE, IN_BASE, IN_COUNT)")
        # Hardware findings 2026-09-15 (fpga-1): wait-gpio needs the absolute
        # GPIO number on this build, and in_base must be relative to gpio_base.
        assert "CLK_PIO_INDEX = CLK_GPIO - GPIO_BASE\n" in script
        script = script.replace("CLK_PIO_INDEX = CLK_GPIO - GPIO_BASE\n", "CLK_PIO_INDEX = CLK_GPIO\n")
        assert "in_base=machine.Pin(IN_BASE))" in script
        script = script.replace("in_base=machine.Pin(IN_BASE))", "in_base=machine.Pin(IN_BASE - GPIO_BASE))")

        header = Header(sample_bits=profile.sample_bits, samples_per_word=profile.samples_per_word,
                        flags=profile.flags, signal_map=profile.signal_map, mode=0,
                        clock_hz=a.clock_hz, desc=f"smoke {a.profile} {a.design} clock={a.clock_hz}")
        fp = open(a.out, "wb")
        Writer(fp, header)

        # send the script and consume the raw-REPL OK
        link.write(script.encode() + b"\x04")
        buf = bytearray()
        t0 = time.time()
        while b"OK" not in buf:
            buf += link.read(0.5)
            if time.time() - t0 > 10:
                print("no OK:", bytes(buf[:200]), file=sys.stderr)
                return 1
        i = buf.index(b"OK")
        del buf[: i + 2]
        n_chunks = 0
        n_bytes = 0
        interrupted = False
        while True:
            try:
                head = read_exact(link, buf, 8, 10.0)
            except TimeoutError as e:
                print("timeout waiting for chunk header:", e, file=sys.stderr)
                link.write(b"\x03")  # interrupt the script so its finally/traceback runs
                t1 = time.time()
                tail = bytearray(buf)
                while b"\x04>" not in tail and time.time() - t1 < 5:
                    tail += link.read(0.5)
                print("tail after interrupt:", bytes(tail[-600:]))
                break
            if head[0] == 4:
                tail = head[1:] + bytes(buf)
                print("end of script output; tail:", tail[:300])
                break
            tag, length = head[:4], struct.unpack("<I", head[4:])[0]
            if tag not in KNOWN or length > 16 * 1024 * 1024:
                print("framing lost at", repr(head), bytes(buf[:64]), file=sys.stderr)
                break
            payload = read_exact(link, buf, length, 10.0)
            fp.write(head + payload)
            n_chunks += 1
            n_bytes += 8 + length
            if tag == b"TIME":
                ml = struct.unpack_from("<H", payload, 16)[0]
                print("TIME:", struct.unpack_from("<QII", payload, 0), payload[18:18 + ml])
            if n_chunks % 20 == 0:
                print(f"{n_chunks} chunks {n_bytes} bytes {n_bytes / (time.time() - t0) / 1024:.1f} KB/s")
            if not interrupted and time.time() - t0 > a.seconds:
                link.write(b"\x03")
                interrupted = True
        fp.close()
        print(f"done: {n_chunks} chunks, {n_bytes} bytes in {time.time() - t0:.1f}s -> {a.out}")
        repl.exec("tt.clock_project_stop()")
    finally:
        try:
            repl.exit()
        finally:
            link.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
