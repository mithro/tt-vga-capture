// ttcap_pack: core 1 of the two-core BIO sampler.
//
// Pops raw 32-bit GPIO snapshots from FIFO0 (written by ttcap_raw on core 0),
// keeps bits 7:0, packs four per word (first sample in bits 7:0) and pushes
// the word to FIFO1 for the host. Core 1 runs from the free-running divider
// (it never waits on a quantum), so it only has to keep up on average; FIFO0
// (8 deep) absorbs the phase difference.

#include <stdint.h>

#include "bio.h" // this must always be first

void main(void) {
    __asm__ volatile (
        "ttcap_pack_loop:\n"
        "mv   a0, x16\n"
        "andi a0, a0, 255\n"
        "mv   a1, x16\n"
        "andi a1, a1, 255\n"
        "slli a1, a1, 8\n"
        "or   a0, a0, a1\n"
        "mv   a1, x16\n"
        "andi a1, a1, 255\n"
        "slli a1, a1, 16\n"
        "or   a0, a0, a1\n"
        "mv   a1, x16\n"
        "slli a1, a1, 24\n"
        "or   a0, a0, a1\n"
        "mv   x17, a0\n"
        "j    ttcap_pack_loop\n"
        ::: "a0", "a1", "memory");
}
