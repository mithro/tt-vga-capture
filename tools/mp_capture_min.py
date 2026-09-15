# SPDX-License-Identifier: Apache-2.0
# Minimal MicroPython capture (exploration, 2026-09-15): PIO sampler + two
# chained DMA channels + module-level hard IRQ handlers, emitting RAW and
# TIME chunks to stdout. The host prepends CFG = {...}. Applies the fpga-1
# findings: PIO1 with its base set for real, absolute wait-gpio index and in_base,
# clock pin untouched, handlers at module level with precomputed addresses.
import sys, rp2, machine, uctypes, struct

CLK = CFG["clk_gpio"]              # noqa: F821
IN_BASE_REL = CFG["in_base"]  # noqa: F821  (absolute: MicroPython subtracts the PIO base itself)
IN_COUNT = CFG["in_count"]         # noqa: F821
PUSH = CFG["push_thresh"]          # noqa: F821
BUF_WORDS = CFG["buf_words"]       # noqa: F821
MAX_CHUNKS = CFG["max_chunks"]     # noqa: F821
PIO_NUM = CFG["pio"]               # noqa: F821
SM_NUM = 0
SAMPLES_PER_WORD = PUSH // IN_COUNT
PIO_BASE = 0x50200000 + 0x100000 * PIO_NUM
RXF = PIO_BASE + 0x20 + 4 * SM_NUM
DREQ = 8 * PIO_NUM + 4 + SM_NUM
FDEBUG = PIO_BASE + 0x8


def make_sampler(clk, n, push):
    @rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_LEFT, autopush=True, push_thresh=push, fifo_join=rp2.PIO.JOIN_RX)
    def sampler():
        wrap_target()
        wait(1, gpio, clk)
        wait(0, gpio, clk)
        in_(pins, n)
        wrap()
    return sampler


mem = machine.mem32
bufs = [bytearray(4 * BUF_WORDS), bytearray(4 * BUF_WORDS)]
addr = [uctypes.addressof(bufs[0]), uctypes.addressof(bufs[1])]
full = [False, False]
overruns = [0]
dma = [rp2.DMA(), rp2.DMA()]
wr = [0x50000000 + 0x40 * dma[0].channel + 4, 0x50000000 + 0x40 * dma[1].channel + 4]
tc = [0x50000000 + 0x40 * dma[0].channel + 8, 0x50000000 + 0x40 * dma[1].channel + 8]
WR0, WR1, TC0, TC1, A0, A1 = wr[0], wr[1], tc[0], tc[1], addr[0], addr[1]


def on0(_c):
    mem[WR0] = A0
    mem[TC0] = BUF_WORDS
    if full[0]:
        overruns[0] += 1
    full[0] = True


def on1(_c):
    mem[WR1] = A1
    mem[TC1] = BUF_WORDS
    if full[1]:
        overruns[0] += 1
    full[1] = True


def time_chunk(msg):
    body = struct.pack("<QIIH", 0, 0, overruns[0] * BUF_WORDS * SAMPLES_PER_WORD, len(msg)) + msg
    sys.stdout.buffer.write(b"TIME" + struct.pack("<I", len(body)) + body)


def main():
    sm = rp2.StateMachine(PIO_NUM * 4 + SM_NUM, make_sampler(CLK, IN_COUNT, PUSH), in_base=machine.Pin(IN_BASE_REL))
    for i in (0, 1):
        ctrl = dma[i].pack_ctrl(size=2, inc_read=False, inc_write=True, treq_sel=DREQ,
                                chain_to=dma[1 - i].channel, irq_quiet=False)
        dma[i].config(read=RXF, write=bufs[i], count=BUF_WORDS, ctrl=ctrl)
        dma[i].irq(on0 if i == 0 else on1, hard=True)
    mem[FDEBUG] = 1 << SM_NUM
    head = b"RAW " + struct.pack("<II", 4 + 4 * BUF_WORDS, BUF_WORDS * SAMPLES_PER_WORD)
    sent = 0
    idx = 0
    try:
        dma[0].active(1)
        sm.active(1)
        while sent < MAX_CHUNKS:
            while not full[idx]:
                machine.idle()
            sys.stdout.buffer.write(head)
            sys.stdout.buffer.write(bufs[idx])
            full[idx] = False
            sent += 1
            idx ^= 1
    finally:
        sm.active(0)
        rxstall = (mem[FDEBUG] >> SM_NUM) & 1
        for d in dma:
            d.active(0)
            d.close()
        time_chunk(b"overruns=%d rxstall=%d chunks=%d" % (overruns[0], rxstall, sent))


main()
