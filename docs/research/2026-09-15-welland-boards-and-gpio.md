# Welland Tiny Tapeout boards, access paths and RP2 GPIO maps

Date: 2026-09-15. Sources are quoted or linked; nothing here is assumed.

## Boards at Welland

From `/etc/fpgas-online/tt-boards.yaml` on `tweed` (rendered by
`fpgas.online-infra` from `ansible/inventory/host_vars/fpgas.online.yml`):

| slug | switch/port | Pi hostname | kind | board |
|---|---|---|---|---|
| tt03p5 | 2/3 | pi-sw2-p3 | asic | TT demo board (RP2040), firmware v1.2.2, legacy Commander |
| tt04 | 2/4 | pi-sw2-p4 | asic | TT demo board (RP2040) |
| tt05 | 2/5 | pi-sw2-p5 | asic | TT demo board (RP2040) |
| tt06 | 2/6 | pi-sw2-p6 | asic | TT demo board (RP2040) |
| tt07 | 2/7 | pi-sw2-p7 | asic | TT demo board (RP2040) |
| tt08 | 2/8 | pi-sw2-p8 | asic | TT demo board (RP2040) |
| tt09, tt10 | 2/9, 2/10 | | asic | disabled |
| fpga-1..4 | 2/33..36 | pi-sw2-p33..36 | fpga | "TT demo board v3 (RP2350, SDK 3.1.0) with the FabricFox FPGA breakout" |

Pi addressing: `pi-sw<switch>-p<port>` at `10.21.<switch>.<port>` (design
spec `fpgas.online-infra/docs/superpowers/specs/2026-08-22-tinytapeout-fpgas-online-design.md`, §3).

## Access

- `ten64.welland.mithis.com` and `tweed.welland.mithis.com` accept SSH as
  `tim`. `tweed` (Debian 13, x86) is the fpgas.online server and can reach
  every Pi and each Pi's daemon on `:8765`.
- `tweed`'s ED25519 host key changed after its 2026-08 rebuild. Verified on
  2026-09-15 by `ssh-keyscan` from `ten64` (inside the network):
  `SHA256:8JMaRRnmbng14uL3q4fD3SvXo00k+mA/wUge9gLN2Ps`, identical to what my
  machine saw, before replacing the stale `~/.ssh/known_hosts` entry.
- The Pis boot a read-only NFS root with a tmpfs overlay; a reboot clears
  all state. Tim has permitted power cycling and rebooting boards and Pis,
  one at a time with a gap.
- Pi accounts: `fpgas.online-infra/ansible/roles/fixpi/tasks/userconf.yml`
  copies the server user's `id_rsa.pub` and the controller key into
  `root` and `pi` `authorized_keys`. User `tim` is refused on the Pis.

## Pi daemon (`fpgas-tt`, repo `fpgas-online/fpgas.online-tt`)

Owns `/dev/ttboard` (udev symlink for USB `2e8a:0005` / `2e8a:000f`) at
115200 baud (irrelevant for USB CDC) and exposes on `0.0.0.0:8765`:

- `GET /health`
- `WS /serial`: fan-out bridge; every client sees every byte; clients more
  than 256 KiB behind are dropped.
- fpga boards: `GET /designs`, `POST /designs/{name}/enable` (`{"clock_hz"}`),
  `POST /bitstream` (multipart `name`, `file`; ≤ 256 KiB; iCE40 preamble
  `7E AA 99 7E` in the first 64 bytes; name `^[a-z0-9_]{1,40}$`; at most 16
  uploads), `POST /demos/sync`.

tweed proxies as `https://tinytapeout.fpgas.online/ws/board/<slug>/serial`
and `/api/board/<slug>/...` (CSRF-protected POSTs).

Tim's rule: this bridge is for debugging and testing; performance captures
must own the serial device on the Pi.

## FPGA emulation boards

FabricFox iCE40UP5K breakout on a demo board v3. Flow from
`TinyTapeout/tt-support-tools/tt_fpga.py`:

```
yosys -p 'read_verilog -sv tt_fpga_top.v <sources>; synth_ice40 -top tt_fpga_top -json out.json'
nextpnr-ice40 --pcf-allow-unconstrained --seed <s> --freq <f> --package sg48 --up5k --asc out.asc --pcf fpga/tt_fpga_fabricfoxv2.pcf --json out.json
icepack out.asc out.bin
```

`fpga/tt_fpga_top.v` instantiates `__tt_um_placeholder` (replaced by the
project's top) with `ena=1`; `uio` goes through `SB_IO` with
`PIN_TYPE 6'b1010_01`. FabricFox v2 pcf: `clk` pin 20, `rst_n` 37,
`uo_out[0..7]` = 38, 42, 43, 44, 45, 46, 47, 48.

## RP2 GPIO maps (tt-micropython-firmware, `src/ttboard/pins/`)

### RP2040 demo boards (`GPIOMapTT06`, tag v2.0.4 `gpio_map.py`)

```
RP_PROJCLK = 0     PROJECT_nRST = 1
CTRL_SEL_nRST = 2  CTRL_SEL_INC = 3  CTRL_SEL_ENA = 4
UO_OUT0..3 = 5, 6, 7, 8
UI_IN0..3  = 9, 10, 11, 12
UO_OUT4..7 = 13, 14, 15, 16
UI_IN4..7  = 17, 18, 19, 20
UIO0..7    = 21..28
```

`GPIOMapTT04` (same file) differs: `SDI_nPROJECT_RST = 3`, `HK_SDO = 4`,
`UO_OUT0 = 5`, `CTRL_ENA_UO_OUT1 = 6`, `nCRST_UO_OUT2 = 7`,
`CINC_UO_OUT3 = 8`; uo_out[1..3] share pins with the mux control lines.
Which of the two maps each Welland RP2040 board uses is determined by the
firmware from the board/shuttle and must be read back from the board
(`tt.pins` in the REPL) before capture.

Consequence for PIO: uo_out is **not contiguous**. One state machine with
`IN_BASE = 5` and `in pins, 12` yields
`[uo3 uo2 uo1 uo0]` in bits 0-3, `ui_in[0..3]` in bits 4-7 (driven by the
RP2040 itself, so known), `[uo7 uo6 uo5 uo4]` in bits 8-11. Alternatively
two state machines, `IN_BASE 5` and `IN_BASE 13`, `in pins, 4` each,
synchronised on the same clock edge.

### RP2350 demo board v3 (`GPIOMapTTDBv3`, main, `gpio_map_dbv3.py`)

```
ANALOG_CURRENT_SOURCE = 12
PROJECT_nRST = 14   MANUAL_PROJCLK = 15   RP_PROJCLK = 16
CTRL_SEL_nRST = 1   CTRL_SEL_INC = 2      CTRL_SEL_ENA = 0
UO_OUT0..7 = 33..40
UI_IN0..7  = 17..24
UIO0..7    = 25..32
MNG00..07 = 3..10   ADC1..5 = 41..45
```

RP2350 PIO sees a 32-pin window starting at `GPIOBASE` (0 or 16). With
`GPIOBASE = 16`: clk is PIO pin 0, uo_out[0..7] are PIO pins 17..24,
contiguous.

## Tiny VGA Pmod

From <https://tinytapeout.com/specs/pinouts/>: uo_out[0]=R1, [1]=G1,
[2]=B1, [3]=vsync, [4]=R0, [5]=G0, [6]=B0, [7]=hsync.

## Candidate projects for the first capture

From `tinytapeout-project-search` (`tt_projects.db`, `pmods LIKE
'%tiny-vga%'`, shuttles tt03p5-tt08, ordered by silicon "working" reports):

| shuttle | macro | title | clock_hz | working reports |
|---|---|---|---|---|
| tt05 | tt_um_flappy_vga_cutout1 | Flappy VGA | 25000000 | 6 |
| tt05 | tt_um_dinogame | VGA Dino Game | (unset) | 6 |
| tt08 | tt_um_a1k0n_nyancat | VGA Nyan Cat | 25175000 | 4 |
| tt08 | tt_um_vga_glyph_mode | Glyph Mode | 25175000 | 4 |
| tt07 | tt_um_tinytapeout_dvd_screensaver | DVD Screensaver with Tiny Tapeout Logo | 25175000 | 3 |
| tt07 | tt_um_rejunity_vga | VGA Checkers | 25200000 | 2 |
| tt08 | tt_um_rejunity_vga_logo | VGA Tiny Logo (1 tile) | 25175000 | 1 |
| tt08 | tt_um_tinytapeout_logo_screensaver | VGA Screensaver with Tiny Tapeout Logo | 25175000 | 1 |

Static or near-static candidates first: VGA Checkers, VGA Tiny Logo, Glyph
Mode (glyphs scroll, but the frame structure is fixed).
