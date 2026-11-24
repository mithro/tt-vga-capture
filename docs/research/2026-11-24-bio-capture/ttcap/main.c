// ttcap: single-core BIO equivalent of the RP2 PIO uo_out sampler.
//
// Wiring assumed (BIO GPIO numbering, not package pins):
//   GPIO 0..7  <- uo_out[0..7]  (data)
//   GPIO 8     <- project clock (core 0's external quantum source, set by host)
//
// The host configures core 0's quantum to come from GPIO 8 ("external" clock
// style, sfr_extclock). The quantum fires on a RISING edge of the synchronised
// pin; for falling-edge sampling the host sets bit 8 of sfr_io_i_inv instead.
//
// Each `mv x20, zero` halts the core until the next quantum; the following
// `mv aN, x21` reads all 32 GPIO inputs. Four samples are packed per 32-bit
// word, first sample in bits 7:0 (vgacap flags bit0 = 0), and pushed to
// FIFO0 (x16) for the host to drain.
//
// Built with bio-sim's sw/build.zig: python -m ziglang build -Dmodule=ttcap

#include <stdint.h>

#include "bio.h" // this must always be first

void main(void) {
    set_gpio_mask(0x1FF);
    set_input_pins(0x1FF);

    __asm__ volatile (
        "ttcap_loop:\n"
        "mv   x20, zero\n"      // wait for clock edge
        "mv   a0, x21\n"        // sample 0
        "andi a0, a0, 255\n"
        "mv   x20, zero\n"
        "mv   a1, x21\n"        // sample 1
        "andi a1, a1, 255\n"
        "slli a1, a1, 8\n"
        "or   a0, a0, a1\n"
        "mv   x20, zero\n"
        "mv   a1, x21\n"        // sample 2
        "andi a1, a1, 255\n"
        "slli a1, a1, 16\n"
        "or   a0, a0, a1\n"
        "mv   x20, zero\n"
        "mv   a1, x21\n"        // sample 3 (upper bits shift out)
        "slli a1, a1, 24\n"
        "or   a0, a0, a1\n"
        "mv   x16, a0\n"        // push packed word to FIFO0
        "j    ttcap_loop\n"
        ::: "a0", "a1", "memory");
}
