import sys, os, gc, rp2, hashlib, uctypes
print("version", sys.version)
print("uname", os.uname().version)
f = rp2.Flash()
n, bs = f.ioctl(4, 0), f.ioctl(5, 0)
print("fs_blocks", n, "block_size", bs, "fs_bytes", n * bs)
try:
    print("VERSION", open("/VERSION").read().strip())
except Exception as e:
    print("VERSION ?", e)
# The firmware region of the XIP-mapped flash, below the filesystem.
FW_END = 0x100C8000
h = hashlib.sha256()
a = 0x10000000
while a < FW_END:
    k = min(4096, FW_END - a)
    h.update(bytes(uctypes.bytearray_at(a, k)))
    a += k
print("fw_sha256", "".join("%02x" % x for x in h.digest()))
gc.collect()
print("free", gc.mem_free())
