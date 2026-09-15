# SPDX-License-Identifier: Apache-2.0
"""Quick numerical look at a vgacap stream: value histogram, hsync/vsync
edge periods, using numpy. Run with the vgacap project environment:

    uv run --project ../vgacap python tools/vgacap_stats.py capture.vgacap
"""
from __future__ import annotations

import collections
import struct
import sys

import numpy as np

from vgacap.stream import parse_header, read_chunks


def unpack(header, words: np.ndarray, n: int) -> np.ndarray:
    spw, bits = header.samples_per_word, header.sample_bits
    mask = (1 << bits) - 1
    out = np.empty(len(words) * spw, dtype=np.uint32)
    for s in range(spw):
        slot = spw - 1 - s if header.flags & 1 else s
        out[s::spw] = (words >> (slot * bits)) & mask
    return out[:n]


def main() -> int:
    data = open(sys.argv[1], "rb").read()
    header = None
    samples = []
    for tag, p in read_chunks(data):
        if tag == "VGCH":
            header = parse_header(p)
        elif tag == "RAW ":
            n = struct.unpack_from("<I", p, 0)[0]
            words = np.frombuffer(p, dtype="<u4", offset=4)
            samples.append(unpack(header, words, n))
        elif tag == "TIME":
            t, clk, dropped, ml = struct.unpack_from("<QIIH", p, 0)
            print("TIME", t, clk, dropped, p[18:18 + ml])
    s = np.concatenate(samples)
    print("header:", header)
    print("samples:", len(s))
    hist = collections.Counter(s.tolist())
    print("top values:", [(hex(v), c) for v, c in hist.most_common(12)])
    m = header.signal_map
    hs = (s >> m[0]) & 1
    vs = (s >> m[1]) & 1
    for name, sig in (("hsync", hs), ("vsync", vs)):
        d = np.diff(sig.astype(np.int8))
        rising = np.flatnonzero(d == 1)
        falling = np.flatnonzero(d == -1)
        print(f"{name}: high {sig.mean():.4f}, rising edges {len(rising)}, falling {len(falling)}")
        if len(rising) > 2:
            per = np.diff(rising)
            print(f"  rising-edge periods: {collections.Counter(per.tolist()).most_common(5)}")
        if len(falling) > 1 and len(rising) > 1:
            # pulse widths for low pulses
            widths = []
            for f in falling[:2000]:
                r = rising[rising > f]
                if len(r):
                    widths.append(int(r[0] - f))
            print(f"  low-pulse widths: {collections.Counter(widths).most_common(5)}")
    # colour activity
    col = s & ~((1 << m[0]) | (1 << m[1]))
    print("nonzero colour fraction:", float((col != 0).mean()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
