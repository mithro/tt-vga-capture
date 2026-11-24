# The vgacap MicroPython module on fpga-1, flashed and restored byte-exact

Date: 2026-11-24 (UTC). Approved by Tim ("any of them is fine") for this
one test, the first that writes a demo board's flash.
- **Board:** fpga-1, pi-sw2-p34, USB serial 4df39a7a6856f86f. It ran
  stock MicroPython b006887db6 with SDK 3.1.0.
- **Image:** vgacap PR #10 (the `mpy/` USER_C_MODULE), built into the
  tt-micropython-firmware fork's branch `vgacap-module`, release
  `dev-vgacap-module`.

## Making it reversible

1. **What the board ran** (`probe_before.txt`, via `fw_probe.py`): the
   firmware region `0x10000000..0x100C8000`, below the 824 x 4096-byte
   littlefs filesystem, read through the flash's memory map, SHA-256
   `69745ff3…`. That is byte-identical to the firmware region of the stock
   v3.1.0 release UF2.
2. **Backups** (`fw_dump.py`, `fs_dump.py`, `unpack_backup.py`,
   `unpack.log`): the 819,200 firmware-region bytes and all 65 files
   (`manifest_before.txt`), streamed as base64 and verified against the
   board's own hashes. Both matched.
3. **The test image** (`uf2tool.py cut`): only the release UF2's 3,200
   blocks below `0x100C8000`, so the filesystem is never written.
   `fs_start.py` confirmed both builds place the filesystem superblock at
   `0x100C8008`, so the new MicroPython would mount the existing files
   rather than reformat them.
4. **The restore image** (`uf2tool.py frombin`): the board's own
   backed-up bytes, same UF2 family `0xe48bff59`. It decodes back to
   exactly the backup.
5. **Flashing** (`flash_uf2.sh`, on the board's Pi): `fpgas-tt` stopped
   (clients 0 only), `mpremote bootloader`, copy to the RP2350 drive,
   wait for MicroPython to enumerate, `fpgas-tt` started again.

## Result

After flashing the module image (`flash_module.log`, `probe_module.txt`):
- the firmware region's SHA-256 was the test image's own, `debaebe7…`;
- MicroPython reported its new build date;
- all 65 files were identical;
- `import vgacap` gave `API 1`, with `frame` and `stream`.

Captures of `tt_um_vgacal_bars`, run as `ttcap capture --firmware
mpy-module` through the board's bridge (`captures.log`):

| capture | board report | result |
|---|---|---|
| frame, 25 MHz, 2 pictures | window 188 lines (3 frames per picture), frames=2 stalls=0 rxstall=0 | both pixel-exact |
| window, 48 lines, 25 MHz | frames=1 | pixel-exact |
| stream, 500 kHz, 4 s | 2,015,232 samples, overruns 0, rxstall 0 | 3 frames pixel-exact; one unbroken stretch (`stream_continuity.log`) |
| `--pio 0` | -- | refused before anything was sent (`pio0_refused.log`) |

The frame window is 188 lines because the module captures into the
largest contiguous heap block (as its README says). DMA control-block
chaining over several blocks, as `frame_rp2.py` and the pico-sdk firmware
do, is not implemented in the module yet.

After restoring (`flash_restore.log`, `probe_after.txt`,
`manifest_after.txt`):
- the firmware region was back to `69745ff3…`, the original;
- MicroPython reported b006887db6, built 2026-08-11;
- all 65 files were identical, and `import vgacap` failed, as on stock;
- after an SDK restart: SDK 3.1.0, idle display `loaded`, clients 0.

No power cycle was needed at any point.

## Second flash: frame capture chained over heap blocks (vgacap PR #11)

The same procedure, with the release asset
`tt-demo-rp2350-vgacap-module-v3.1.1-dev-14a09314.uf2` (sha256 `6d2308a6…`),
built from vgacap `mpy-chain` 5d84564. `frame()` now spreads a capture
over several heap blocks and chains the DMA through them, as
`frame_rp2.py` does.
- Before flashing, the board again matched the backup: firmware
  `69745ff3…` and all files identical.
- After flashing, the firmware region was `5dc230b2…`, the image's own;
  `import vgacap` gave API 1; the files were unchanged.

| capture | board report | result |
|---|---|---|
| frame, 25 MHz, 2 pictures | **window 481 lines, buffers=46**, frames=2 stalls=0 | both pixel-exact: one captured frame per picture (was 3) |
| window, 48 lines | frames=1 | pixel-exact |
| stream, 500 kHz, 4 s | overruns 0, rxstall 0 | 3 frames pixel-exact; 2,015,232 samples unbroken |

Then the original bytes were restored (`flash_restore_chain.log`,
`probe_after_chain.txt`): the firmware hash, build date and all 65 files
matched the first backup exactly; `vgacap` was absent; SDK 3.1.0; idle
display `loaded`. No power cycle was needed.

The same session also ran the pico-sdk RAM firmware from that branch,
whose frame engine now goes through the same control-block path (one
block plus the stopper). Frame (481 lines, 1 buffer), window and stream
were all pixel-exact, 9 of 9 pictures.
