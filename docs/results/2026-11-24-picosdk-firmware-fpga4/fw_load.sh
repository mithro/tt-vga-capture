#!/bin/bash
# Step A on the fpga-4 Pi: stop fpgas-tt (0 clients only), BOOTSEL, load the
# no_flash capture firmware. Leaves fpgas-tt stopped and the firmware running
# for step B; step C (fw_restore.sh) puts everything back. On any failure
# here, it restores at once.
set -u
cd ~/vgacap-run
log=~/vgacap-run/load.log
: > "$log"
say() { echo "$(date -u +%T) $*" >> "$log"; }
export UV_PYTHON_PREFERENCE=only-system UV_CACHE_DIR=~/vgacap-run/uvcache
ttcap() {
    PYTHONPATH=python timeout 150 ./uv/uv run --no-project --python /usr/bin/python3.11 \
        --with pyserial --with websockets python -m ttcap.cli "$@" >> "$log" 2>&1
    local rc=$?
    say "rc=$rc for: ttcap $*"
    return $rc
}
fail() { say "FAILED: $*"; sudo -n systemctl start fpgas-tt >> "$log" 2>&1; say "fpgas-tt $(systemctl is-active fpgas-tt)"; cat "$log"; exit 1; }

clients=$(curl -s --max-time 5 localhost:8765/health | grep -o '"clients": [0-9]*')
say "before: $clients"
[ "$clients" = '"clients": 0' ] || { say "REFUSED: bridge has clients"; cat "$log"; exit 1; }
say "stopping fpgas-tt"
sudo -n systemctl stop fpgas-tt >> "$log" 2>&1
ttcap reboot serial:/dev/ttboard --to bootsel || fail "bootsel"
dev=""
for i in $(seq 1 30); do
    dev=$(readlink -f /dev/disk/by-label/RP2350 2>&1 | grep "^/dev/sd")
    [ -n "$dev" ] && break
    sleep 1
done
[ -n "$dev" ] || fail "no BOOTSEL drive"
sudo -n mkdir -p /mnt/rp2350
sudo -n mount "$dev" /mnt/rp2350 >> "$log" 2>&1
sudo -n cp vgacap_fw.uf2 /mnt/rp2350/ >> "$log" 2>&1
sync
sudo -n umount /mnt/rp2350 >> "$log" 2>&1
FW=""
for i in $(seq 1 30); do
    FW=$(ls /dev/serial/by-id/usb-vgacap_vgacap_capture_firmware_*-if00 2>&1 | grep -v "No such")
    [ -n "$FW" ] && break
    sleep 1
done
say "firmware port: ${FW:-none}"
cat "$log"
