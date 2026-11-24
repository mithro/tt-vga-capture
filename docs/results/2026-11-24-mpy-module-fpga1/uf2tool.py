"""Minimal UF2 tool: inspect, cut to an address range, build from a binary.

    uf2tool.py info FILE
    uf2tool.py cut IN OUT END          keep blocks whose target addr < END
    uf2tool.py frombin BIN OUT BASE FAMILY
    uf2tool.py tobin UF2 OUT BASE END  (blocks in [BASE, END), 0xFF where absent)
"""
import struct
import sys

MAGIC0, MAGIC1, MAGIC_END = 0x0A324655, 0x9E5D5157, 0x0AB16F30
FLAG_FAMILY = 0x00002000


def blocks(data):
    assert len(data) % 512 == 0, len(data)
    for i in range(0, len(data), 512):
        b = data[i:i + 512]
        m0, m1, flags, addr, size, seq, total, fam = struct.unpack_from("<8I", b, 0)
        (mend,) = struct.unpack_from("<I", b, 508)
        assert m0 == MAGIC0 and m1 == MAGIC1 and mend == MAGIC_END, i
        yield flags, addr, size, seq, total, fam, b


def info(path):
    data = open(path, "rb").read()
    fams, lo, hi, n = {}, None, None, 0
    for flags, addr, size, seq, total, fam, _ in blocks(data):
        n += 1
        fams[hex(fam)] = fams.get(hex(fam), 0) + 1
        lo = addr if lo is None else min(lo, addr)
        hi = addr + size if hi is None else max(hi, addr + size)
    print("%s: %d blocks, families %s, range %s..%s" % (path, n, fams, hex(lo), hex(hi)))


def write(out, items, family):
    total = len(items)
    with open(out, "wb") as f:
        for seq, (addr, payload) in enumerate(items):
            assert len(payload) == 256
            head = struct.pack("<8I", MAGIC0, MAGIC1, FLAG_FAMILY, addr, 256, seq, total, family)
            body = payload + b"\0" * (476 - 256)
            f.write(head + body + struct.pack("<I", MAGIC_END))


def cut(src, out, end):
    data = open(src, "rb").read()
    keep, fam = [], None
    for flags, addr, size, seq, total, family, b in blocks(data):
        if addr + size <= end:
            assert size == 256 and flags & FLAG_FAMILY, (hex(addr), size, flags)
            keep.append((addr, b[32:32 + 256]))
            fam = family if fam is None else fam
            assert family == fam
    write(out, keep, fam)
    print("kept", len(keep), "blocks below", hex(end), "family", hex(fam))


def frombin(binpath, out, base, family):
    data = open(binpath, "rb").read()
    assert len(data) % 256 == 0
    write(out, [(base + i, data[i:i + 256]) for i in range(0, len(data), 256)], family)
    print("wrote", len(data) // 256, "blocks from", hex(base), "family", hex(family))


def tobin(src, out, base, end):
    img = bytearray(b"\xff" * (end - base))
    for flags, addr, size, seq, total, fam, b in blocks(open(src, "rb").read()):
        if base <= addr and addr + size <= end:
            img[addr - base:addr - base + size] = b[32:32 + size]
    open(out, "wb").write(bytes(img))


cmd = sys.argv[1]
if cmd == "info":
    info(sys.argv[2])
elif cmd == "cut":
    cut(sys.argv[2], sys.argv[3], int(sys.argv[4], 0))
elif cmd == "frombin":
    frombin(sys.argv[2], sys.argv[3], int(sys.argv[4], 0), int(sys.argv[5], 0))
elif cmd == "tobin":
    tobin(sys.argv[2], sys.argv[3], int(sys.argv[4], 0), int(sys.argv[5], 0))
