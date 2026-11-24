#!/bin/bash
# Run on the fpga-4 Pi: the pico-sdk capture firmware from RAM (no_flash UF2).
# fpgas-tt is stopped only with no bridge clients; the EXIT trap always sends
# the board back to its flash firmware and starts fpgas-tt again.
set -u
cd ~/vgacap-run
log=~/vgacap-run/fw.log
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
fw_port() { ls /dev/serial/by-id/usb-vgacap_vgacap_capture_firmware_*-if00 2>&1 | grep -v "No such"; }

clients=$(curl -s --max-time 5 localhost:8765/health | grep -o '"clients": [0-9]*')
say "before: $clients"
if [ "$clients" != '"clients": 0' ]; then say "REFUSED: bridge has clients"; cat "$log"; exit 1; fi

back_to_stock() {
    FW=$(fw_port)
    if [ -n "$FW" ]; then
        ttcap reboot "serial:$FW" --firmware picosdk
    fi
    for i in $(seq 1 30); do
        [ -e /dev/ttboard ] && break
        sleep 1
    done
    say "after reboot: ttboard=$(ls -la /dev/ttboard 2>&1 | cut -c1-80)"
    say "usb: $(lsusb | grep -i 2e8a)"
    sudo -n systemctl start fpgas-tt >> "$log" 2>&1
    say "fpgas-tt $(systemctl is-active fpgas-tt)"
    cat "$log"
}
trap back_to_stock EXIT

say "stopping fpgas-tt"
sudo -n systemctl stop fpgas-tt >> "$log" 2>&1
say "fpgas-tt $(systemctl is-active fpgas-tt)"

# A stock-firmware reference capture of the same design, for comparison.
ttcap capture serial:/dev/ttboard --project tt_um_rejunity_vga_logo --mode frame --clock-hz 25175000 --frames 2 --out ref_frame.vgacap

ttcap reboot serial:/dev/ttboard --to bootsel
dev=""
for i in $(seq 1 30); do
    dev=$(readlink -f /dev/disk/by-label/RP2350 2>&1 | grep "^/dev/sd")
    [ -n "$dev" ] && break
    sleep 1
done
say "bootsel drive: ${dev:-none}; usb: $(lsusb | grep -i 2e8a)"
if [ -z "$dev" ]; then say "NO BOOTSEL DRIVE"; exit 2; fi
sudo -n mkdir -p /mnt/rp2350
sudo -n mount "$dev" /mnt/rp2350 >> "$log" 2>&1
say "INFO_UF2: $(cat /mnt/rp2350/INFO_UF2.TXT 2>&1 | tr '\n' ' ')"
sudo -n cp vgacap_fw.uf2 /mnt/rp2350/ >> "$log" 2>&1
sync
sudo -n umount /mnt/rp2350 >> "$log" 2>&1
for i in $(seq 1 30); do
    FW=$(fw_port)
    [ -n "$FW" ] && break
    sleep 1
done
say "firmware port: ${FW:-none}; usb: $(lsusb | grep -i 2e8a)"
if [ -z "$FW" ]; then say "FIRMWARE DID NOT ENUMERATE"; exit 3; fi

ttcap capture --firmware picosdk "serial:$FW" --clock-hz 25175000 --mode frame --frames 2 --asic-index 806 --out fw_frame.vgacap
ls -la ref_frame.vgacap fw_frame.vgacap >> "$log" 2>&1
