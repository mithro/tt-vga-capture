// ttcap_raw: core 0 of the two-core BIO sampler.
//
// The host points core 0's external quantum at the project-clock pin
// (GPIO 8 in the byte layout, GPIO 27 in the Dabao layout). The loop is two
// instructions per sample: wait for the edge, then move all 32 GPIO inputs
// straight into FIFO0. Core 1 (ttcap_pack or ttcap_pack16) extracts and
// packs the uo_out bits onto FIFO1. This core only reads, so it makes every
// pin an input and does not need to know the layout.

#include <stdint.h>

#include "bio.h" // this must always be first

void main(void) {
    set_gpio_mask(0xFFFFFFFF);
    set_input_pins(0xFFFFFFFF);

    __asm__ volatile (
        "ttcap_raw_loop:\n"
        "mv x20, zero\n"
        "mv x16, x21\n"
        "mv x20, zero\n"
        "mv x16, x21\n"
        "mv x20, zero\n"
        "mv x16, x21\n"
        "mv x20, zero\n"
        "mv x16, x21\n"
        "j  ttcap_raw_loop\n"
        ::: "memory");
}
