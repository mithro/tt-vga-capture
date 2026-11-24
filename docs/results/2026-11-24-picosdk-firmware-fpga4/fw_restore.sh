#!/bin/bash
# Step C on the fpga-4 Pi: watchdog reboot of the capture firmware back to
# the stock flash firmware, then fpgas-tt started again. Safe to run twice.
set -u
cd ~/vgacap-run
log=~/vgacap-run/restore.log
: > "$log"
say() { echo "$(date -u +%T) $*" >> "$log"; }
export UV_PYTHON_PREFERENCE=only-system UV_CACHE_DIR=~/vgacap-run/uvcache
FW=$(ls /dev/serial/by-id/usb-vgacap_vgacap_capture_firmware_*-if00 2>&1 | grep -v "No such")
if [ -n "$FW" ]; then
    PYTHONPATH=python timeout 60 ./uv/uv run --no-project --python /usr/bin/python3.11 \
        --with pyserial --with websockets python -m ttcap.cli reboot "serial:$FW" --firmware picosdk >> "$log" 2>&1
    say "reboot rc=$?"
fi
for i in $(seq 1 30); do
    [ -e /dev/ttboard ] && break
    sleep 1
done
say "ttboard: $(ls -la /dev/ttboard 2>&1 | cut -c1-80); usb: $(lsusb | grep -i 2e8a)"
sudo -n systemctl start fpgas-tt >> "$log" 2>&1
say "fpgas-tt $(systemctl is-active fpgas-tt)"
cat "$log"
