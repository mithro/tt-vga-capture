# MicroPython: how fast can the RP2 run-length encode a DMA buffer on its CPU?
# One-byte samples (RP2350 layout), 640x480@60 bars lines with their syncs.
import time
import micropython
import gc

N = 16384  # one 4096-word DMA buffer of 8-bit samples


def make_buf():
    buf = bytearray(N)
    for i in range(N):
        x = i % 800
        if 656 <= x < 752:
            buf[i] = 0x08  # hsync pulse (negative: bit 7 low), vsync idle high
        elif x < 640:
            buf[i] = 0x88 | ((x // 10) & 0x37)
        else:
            buf[i] = 0x88
    return buf


def rle_py(src, n, out):
    k = 0
    prev = src[0]
    run = 1
    for i in range(1, n):
        v = src[i]
        if v == prev:
            run += 1
        else:
            out[k] = prev
            out[k + 1] = run
            k += 2
            prev = v
            run = 1
    out[k] = prev
    out[k + 1] = run
    return k + 2


@micropython.native
def rle_native(src, n, out):
    k = 0
    prev = src[0]
    run = 1
    for i in range(1, n):
        v = src[i]
        if v == prev:
            run += 1
        else:
            out[k] = prev
            out[k + 1] = run
            k += 2
            prev = v
            run = 1
    out[k] = prev
    out[k + 1] = run
    return k + 2


@micropython.viper
def rle_viper(src: ptr8, n: int, out: ptr32) -> int:
    k = 0
    prev = src[0]
    run = 1
    i = 1
    while i < n:
        v = src[i]
        if v == prev:
            run += 1
        else:
            out[k] = prev
            out[k + 1] = run
            k += 2
            prev = v
            run = 1
        i += 1
    out[k] = prev
    out[k + 1] = run
    return k + 2


buf = make_buf()
out = bytearray(4 * 2 * N)  # worst case: a pair per sample, u32 each
import array
out32 = array.array("I", bytes(4 * 2 * 2048))
gc.collect()
import machine
print("sysclk", machine.freq())
for name, fn, dest in (("python", rle_py, array.array("I", bytes(4 * 2 * 2048))),
                       ("native", rle_native, array.array("I", bytes(4 * 2 * 2048))),
                       ("viper", rle_viper, out32)):
    t0 = time.ticks_us()
    words = fn(buf, N, dest)
    dt = time.ticks_diff(time.ticks_us(), t0)
    print(name, "pairs", words // 2, "us", dt, "samples_per_s", N * 1000000 // dt,
          "bytes_in", N, "bytes_out", 4 * words)
