#!/bin/bash
# Run on the fpga-4 Pi: direct serial ownership (stop fpgas-tt, capture on
# /dev/ttboard, start fpgas-tt again -- always, via the EXIT trap).
set -u
cd ~/vgacap-run
log=~/vgacap-run/direct.log
: > "$log"
clients=$(curl -s --max-time 5 localhost:8765/health | grep -o '"clients": [0-9]*')
echo "before: $clients" >> "$log"
if [ "$clients" != '"clients": 0' ]; then
    echo "REFUSED: the bridge has clients" >> "$log"
    cat "$log"
    exit 1
fi
restart() {
    sudo -n systemctl start fpgas-tt >> "$log" 2>&1
    echo "after: fpgas-tt $(systemctl is-active fpgas-tt)" >> "$log"
    date -u +"restarted %FT%TZ" >> "$log"
    cat "$log"
}
trap restart EXIT
date -u +"stopping %FT%TZ" >> "$log"
sudo -n systemctl stop fpgas-tt >> "$log" 2>&1
echo "fpgas-tt $(systemctl is-active fpgas-tt)" >> "$log"
export UV_PYTHON_PREFERENCE=only-system UV_CACHE_DIR=~/vgacap-run/uvcache
run() {
    PYTHONPATH=python timeout 120 ./uv/uv run --no-project --python /usr/bin/python3.11 \
        --with pyserial --with websockets python -m ttcap.cli "$@" >> "$log" 2>&1
    echo "rc=$? for: $*" >> "$log"
}
run throughput serial:/dev/ttboard
run capture serial:/dev/ttboard --clock-hz 750000 --seconds 4 --out ~/vgacap-run/direct_bars.vgacap
ls -la ~/vgacap-run/direct_bars.vgacap >> "$log" 2>&1
