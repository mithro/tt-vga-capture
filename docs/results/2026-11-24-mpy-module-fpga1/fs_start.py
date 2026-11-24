"""Where does each UF2's filesystem image start? Look for littlefs superblocks."""
import struct
import sys

for path in sys.argv[1:]:
    data = open(path, "rb").read()
    hits = []
    for i in range(0, len(data), 512):
        addr, size = struct.unpack_from("<II", data, i + 12)
        payload = data[i + 32:i + 32 + size]
        j = payload.find(b"littlefs")
        if j >= 0:
            hits.append(hex(addr + j))
    print(path, "littlefs magic at", hits[:4])
