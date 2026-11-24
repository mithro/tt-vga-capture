"""Turn the board dumps into files and check them against the board's hashes.

    unpack_backup.py FW_DUMP FS_DUMP MANIFEST PROBE OUTDIR
"""
import base64
import hashlib
import pathlib
import sys

fw_dump, fs_dump, manifest, probe, outdir = sys.argv[1:6]
out = pathlib.Path(outdir)
out.mkdir(parents=True, exist_ok=True)

# Firmware region.
blob = bytearray()
expect = 0x10000000
ended = False
for line in pathlib.Path(fw_dump).read_text().splitlines():
    if line.startswith("B"):
        addr, b64 = line[1:].split(" ", 1)
        assert int(addr, 16) == expect, (addr, hex(expect))
        chunk = base64.b64decode(b64)
        blob += chunk
        expect += len(chunk)
    elif line.strip() == "END":
        ended = True
assert ended and expect == 0x100C8000, hex(expect)
want = [l.split()[1] for l in pathlib.Path(probe).read_text().splitlines() if l.startswith("fw_sha256")][0]
got = hashlib.sha256(blob).hexdigest()
print("firmware region", len(blob), "bytes, sha256", got, "MATCH" if got == want else "MISMATCH " + want)
(out / "firmware_region.bin").write_bytes(bytes(blob))

# Files.
hashes = {}
for line in pathlib.Path(manifest).read_text().splitlines():
    if line.startswith("F "):
        _, path, size, h = line.split(" ")
        hashes[path] = (int(size), h)
cur, data, ok, bad = None, bytearray(), 0, []
dirs = []
for line in pathlib.Path(fs_dump).read_text().splitlines():
    if line.startswith("D "):
        dirs.append(line[2:])
    elif line.startswith("F "):
        cur, data = line[2:], bytearray()
    elif line.startswith("C "):
        data += base64.b64decode(line[2:])
    elif line == "E":
        size, h = hashes[cur]
        if len(data) == size and hashlib.sha256(data).hexdigest() == h:
            ok += 1
        else:
            bad.append(cur)
        dest = out / "fs" / cur.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bytes(data))
(out / "dirs.txt").write_text("\n".join(dirs) + "\n")
print("files", ok, "match the manifest;", len(bad), "do not", bad, "; manifest has", len(hashes))
