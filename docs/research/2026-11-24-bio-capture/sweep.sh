#!/usr/bin/env bash
# Re-run every bio-sim capture experiment in the research note.
#
#   sweep.sh /path/to/bio-sim /path/to/logdir
#
# Needs: the `bio-sim` docker image (see the note's "Building" section) and
# the four programs built into <bio-sim>/sw/<name>/<name>.bin. Each run
# writes <logdir>/<name>.log (sim stdout) and <name>.err.log (progress bar);
# one JSON result line per run goes to <logdir>/all.out.
set -euo pipefail
SIM="$1"
LOGDIR="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
T="$HERE/run_capture_test.py"
mkdir -p "$LOGDIR"
JOBS="$LOGDIR/jobs.txt"
: > "$JOBS"
for tco in 0 1 2 3 4 5 6 7 8 10 12 14 16; do
    echo "--mode single --edge rise --period 28 --tco $tco --clocks 192 --name tco-single-rise-$tco" >> "$JOBS"
    echo "--mode single --edge rise --period 28 --tco $tco --clocks 192 --sync-bypass --name tco-single-rise-sb-$tco" >> "$JOBS"
    echo "--mode dual --edge rise --period 28 --tco $tco --clocks 192 --name tco-dual-rise-$tco" >> "$JOBS"
done
for p in 40 28 24 23 22 21 20 18 17.5 16 14 13 12 11 10.5 10 9 8; do
    for m in single dual; do
        for e in rise fall; do
            echo "--mode $m --edge $e --period $p --tco 2 --clocks 480 --name rate-$m-$e-p$p" >> "$JOBS"
        done
    done
    for e in rise fall; do
        echo "--mode dual16 --layout dabao --edge $e --period $p --tco 2 --clocks 480 --name rate-dual16-$e-p$p" >> "$JOBS"
    done
done
echo "--mode dual --edge fall --period 17.5 --tco 2 --clocks 4800 --seed 7 --name long-dual-fall-40MHz" >> "$JOBS"
echo "--mode dual16 --layout dabao --edge fall --period 17.5 --tco 2 --clocks 4800 --seed 7 --name long-dual16-dabao-fall-40MHz" >> "$JOBS"
echo "--mode single --edge fall --period 28 --tco 2 --clocks 4800 --seed 7 --name long-single-fall-25MHz" >> "$JOBS"
# Runs past the rate limit fail by design, so xargs exits 123; the JSON
# lines in all.out (summarised below) are the result.
xargs -P 70 -L 1 uv run --no-project "$T" --sim "$SIM" --logdir "$LOGDIR" < "$JOBS" > "$LOGDIR/all.out" 2>&1 || true
uv run --no-project "$HERE/summarise.py" "$LOGDIR/all.out" > "$LOGDIR/tables.md"
