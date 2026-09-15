# SPDX-License-Identifier: Apache-2.0
"""Probe a Welland Tiny Tapeout board's MicroPython REPL through the fpgas-tt
WebSocket bridge (debug/test path only).

Usage:
    uv run --with websockets tools/tt_repl_probe.py ws://127.0.0.1:18765/serial [code...]

Set up the tunnel first, e.g.:
    ssh -f -N -L 18765:10.21.2.7:8765 tweed.welland.mithis.com

Sends Ctrl-C twice, enters raw REPL (Ctrl-A), runs each code snippet with
Ctrl-D, prints the output, then returns to the friendly REPL (Ctrl-B).
"""
from __future__ import annotations

import asyncio
import sys

import websockets

DEFAULT_CODE = [
    "import sys, os; print(sys.version); print(sys.implementation); print(os.uname())",
    "import rp2; print('DMA' in dir(rp2), 'PIO' in dir(rp2), 'StateMachine' in dir(rp2))",
    "import machine; print('freq', machine.freq())",
    "import gc; gc.collect(); print('mem_free', gc.mem_free(), 'mem_alloc', gc.mem_alloc())",
    "import ttboard; print('ttboard', ttboard.VERSION if hasattr(ttboard,'VERSION') else '?')",
    "from ttboard.pins.gpio_map import GPIOMap; print({k: v for k, v in GPIOMap.all().items()})",
    "print(tt.shuttle.run if hasattr(tt.shuttle,'run') else tt.shuttle)",
    "print('clock', tt.clock_project_PWM if hasattr(tt,'clock_project_PWM') else None)",
]


async def raw_exec(ws, code: str, timeout: float = 5.0) -> str:
    await ws.send(code.encode() + b"\x04")
    out = b""
    try:
        while not out.endswith(b"\x04>"):
            out += await asyncio.wait_for(ws.recv(), timeout)
    except asyncio.TimeoutError:
        out += b"<TIMEOUT>"
    return out.decode(errors="replace")


async def main(url: str, snippets: list[str]) -> None:
    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(b"\x03\x03")
        await asyncio.sleep(0.3)
        await ws.send(b"\x01")  # raw REPL
        await asyncio.sleep(0.3)
        try:
            while True:
                await asyncio.wait_for(ws.recv(), 0.3)
        except asyncio.TimeoutError:
            pass
        for code in snippets:
            print(f">>> {code}")
            print(await raw_exec(ws, code))
        await ws.send(b"\x02")  # back to friendly REPL


if __name__ == "__main__":
    url = sys.argv[1]
    code = [open(a[1:]).read() if a.startswith("@") else a for a in sys.argv[2:]] or DEFAULT_CODE
    asyncio.run(main(url, code))
