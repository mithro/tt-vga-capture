#!/bin/bash
# On the fpga-1 Pi: write ~/vgacap-run/$1 (a firmware-only UF2) to the board.
# fpgas-tt is stopped only with no bridge clients and is always started
# again; the board comes back under whatever firmware the UF2 holds.
set -u
UF2=~/vgacap-run/$1
log=~/vgacap-run/flash-$1.log
: > "$log"
say() { echo "$(date -u +%T) $*" >> "$log"; }
done_() { sudo -n systemctl start fpgas-tt >> "$log" 2>&1; say "fpgas-tt $(systemctl is-active fpgas-tt)"; cat "$log"; }
trap done_ EXIT
say "uf2 $(sha256sum "$UF2" | cut -c1-64)"
clients=$(curl -s --max-time 5 localhost:8765/health | grep -o '"clients": [0-9]*')
say "before: $clients"
[ "$clients" = '"clients": 0' ] || { say "REFUSED: bridge has clients"; exit 1; }
sudo -n systemctl stop fpgas-tt >> "$log" 2>&1
say "fpgas-tt $(systemctl is-active fpgas-tt)"
timeout 30 mpremote connect /dev/ttboard bootloader >> "$log" 2>&1
say "mpremote bootloader rc=$?"
dev=""
for i in $(seq 1 30); do
    dev=$(readlink -f /dev/disk/by-label/RP2350 2>&1 | grep "^/dev/sd")
    [ -n "$dev" ] && break
    sleep 1
done
say "bootsel drive: ${dev:-none}; usb: $(lsusb | grep -i 2e8a)"
[ -n "$dev" ] || { say "NO BOOTSEL DRIVE"; exit 2; }
sudo -n mkdir -p /mnt/rp2350
sudo -n mount "$dev" /mnt/rp2350 >> "$log" 2>&1
sudo -n cp "$UF2" /mnt/rp2350/ >> "$log" 2>&1
say "copied rc=$?"
sync
sudo -n umount /mnt/rp2350 >> "$log" 2>&1
for i in $(seq 1 60); do
    lsusb | grep -q "2e8a:0005" && [ -e /dev/ttboard ] && break
    sleep 1
done
say "after: usb: $(lsusb | grep -i 2e8a); ttboard: $(ls -la /dev/ttboard 2>&1 | cut -c1-70)"
sleep 3
