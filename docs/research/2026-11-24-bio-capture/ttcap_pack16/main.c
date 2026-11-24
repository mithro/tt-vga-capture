// ttcap_pack16: core 1 packer for the Dabao pin layout.
//
// The Dabao board breaks out BIO16-19 (PC0-PC3) and BIO23-29 (PC7-PC13) but
// not BIO20-22, so no eight broken-out BIO pins are contiguous. Instead of
// gathering bits on the BIO, keep the upper half of each raw GPIO snapshot
// (BIO16..BIO31) and pack two 16-bit samples per word, first sample in bits
// 15:0. The vgacap header's signal_map then names which of the 16 bits carry
// hsync, vsync and colour (sample_bits = 16, samples_per_word = 2).
//
// Layout tested: uo_out[3:0] on BIO16-19, uo_out[7:4] on BIO23-26,
// project clock on BIO27 (sample bits 0-3, 7-10; clock at sample bit 11).

#include <stdint.h>

#include "bio.h" // this must always be first

void main(void) {
    __asm__ volatile (
        "lui  a2, 0xffff0\n"     // a2 = 0xFFFF0000
        "ttcap_pack16_loop:\n"
        "mv   a0, x16\n"         // sample 0: BIO31..16 -> bits 15:0
        "srli a0, a0, 16\n"
        "mv   a1, x16\n"         // sample 1: BIO31..16 stays in bits 31:16
        "and  a1, a1, a2\n"
        "or   a0, a0, a1\n"
        "mv   x17, a0\n"
        "mv   a0, x16\n"         // unrolled once more
        "srli a0, a0, 16\n"
        "mv   a1, x16\n"
        "and  a1, a1, a2\n"
        "or   a0, a0, a1\n"
        "mv   x17, a0\n"
        "j    ttcap_pack16_loop\n"
        ::: "a0", "a1", "a2", "memory");
}
