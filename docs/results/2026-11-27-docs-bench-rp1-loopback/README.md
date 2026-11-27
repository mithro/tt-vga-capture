# vgacap-rp1 docs bench run: the loopback fixture on a Raspberry Pi 5

Date: 2026-11-27. The bench run of vgacap PR #46 (`capture-rp1/how-to-build.md` and
`capture-rp1/how-to-capture-loopback.md`), executed as written at vgacap ad7c418.
Both pages passed with no stops.

## The board

| Item | Value |
|---|---|
| Host | pi-sw2-p38 |
| Model | Raspberry Pi 5 Model B Rev 1.1 |
| Serial | `80ba29ff33528664` |
| Kernel | 6.12.109+rpt-rpi-v8 (aarch64) |
| PIO device | `/dev/pio0`, group `gpio` |

Source: [`identity.log`](identity.log).

## The empty header

Each of GPIO 4 to GPIO 12 was set as an input with its default pull and read,
then put back as found (function `no`). Nothing on the header pulls against the
defaults: GPIO 4 to GPIO 8 read 1 (pull-up), GPIO 9 to GPIO 12 read 0
(pull-down). Source: [`header.log`](header.log).

## The build (`how-to-build.md`)

| Item | Value |
|---|---|
| piolib | raspberrypi/utils `05e8808e84ed99b168b14a4025dddb9118fa1c17` |
| Compiler output | no warnings at `-O2 -Wall -Wextra` |
| `vgacap-rp1` with no arguments | the usage line on the page, exit status 2 |
| `vgacap-rp1-programs 12 rising 3` | `sampler 200c 208c 4008`, as on the page |

Source: [`build.log`](build.log).

## The loopback capture (`how-to-capture-loopback.md`)

Step 1, `vgacap-rp1 --out counter.vgacap --samples 4194304 --gen-counter --gen-div 50 --clock-hz 500000`:

```text
rp1 samples=4194304 seconds=8.460 samples_per_s=495791 dropped=0
```

Step 2, `python3 capture-rp1/check_counter.py counter.vgacap`:

```text
ok: 4194304 samples, every step -1
```

So `--gen-div 50` at the default `--gen-delay 3` ran the generator at 495,791
samples a second, measured by the tool over the whole capture. Source:
[`loopback.log`](loopback.log).

## Releasing the pins

After the capture, GPIO 4 to GPIO 12 were left on function `a7` (PIO).
`for n in 4 5 6 7 8 9 10 11 12; do sudo pinctrl set $n no; done` put them back to
`no`, as found. Source: [`release.log`](release.log) (the loop and `pinctrl get 4-12`; the
same log shows the work directory removed and nothing left holding
`/dev/pio0`).
