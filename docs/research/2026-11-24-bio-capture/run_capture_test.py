# /// script
# requires-python = ">=3.11"
# ///
"""Drive bio-sim (baochip/bio-sim, Verilator model of the real bio_bdma RTL)
with a synthetic Tiny Tapeout clock + uo_out waveform and check the BIO
capture programs return exactly the injected bytes.

Waveform model (all times in BIO aclk cycles, fclk = 700 MHz by default):
  * GPIO 8 = project clock (byte layout; see LAYOUTS). Rising edge k at round(k * period).
    Falling edge at round(k * period + period / 2).
  * GPIO 0..7 = uo_out (byte layout). The byte for project cycle k (data[k], random) is
    driven `tco` aclk cycles after rising edge k, i.e. it changes like a
    registered output would.

The harness only pops FIFOs through APB with stimulus frozen, so the run is
split into chunks of `chunk` project clocks (<= 6 packed words, under the
8-deep FIFO) with a fifo_drain after each. Stimulus is scheduled in absolute
sim cycles; time spent inside a drain does not advance the inject clock, so
the waveform simply pauses (pins frozen) while the host drains.

Check: the captured byte stream must equal data[o], data[o+1], ... for some
start offset o (edges before the core reaches its first wait are not
captured), with no gaps or repeats.

Usage:
  uv run --no-project run_capture_test.py --sim /path/to/bio-sim \
      --mode single --edge rise --period 28 --tco 2 --clocks 480
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

# Pin layouts (BIO GPIO numbers). "byte": uo_out on BIO0-7, clock on BIO8
# (contiguous; needs a board that breaks those out, e.g. longbao).
# "dabao": only pins the Dabao board breaks out: uo_out[3:0] on BIO16-19
# (PC0-3), uo_out[7:4] on BIO23-26 (PC7-10), clock on BIO27 (PC11).
LAYOUTS = {
    "byte": {"data": [0, 1, 2, 3, 4, 5, 6, 7], "clk": 8},
    "dabao": {"data": [16, 17, 18, 19, 23, 24, 25, 26], "clk": 27},
}
# mode -> (core programs, output FIFO bank, samples per word, sample bits,
#          BIO bit of sample bit 0)
MODES = {
    "single": ([("ttcap", "external")], 0, 4, 8, 0),
    "dual": ([("ttcap_raw", "external"), ("ttcap_pack", "fixed")], 1, 4, 8, 0),
    "dual16": ([("ttcap_raw", "external"), ("ttcap_pack16", "fixed")], 1, 2, 16, 16),
}


def build_config(args, data):
    lay = LAYOUTS[args.layout]
    clk_pin = lay["clk"]
    events = []
    n = len(data)
    for k in range(n):
        rise = round(k * args.period)
        fall = round(k * args.period + args.period / 2)
        events.append((rise, clk_pin, 1))
        events.append((fall, clk_pin, 0))
        t = rise + args.tco
        for b, pin in enumerate(lay["data"]):
            events.append((t, pin, (data[k] >> b) & 1))
    events.sort(key=lambda e: e[0])

    progs, bank, _, _, _ = MODES[args.mode]
    cmds = []
    start_cores = []
    for core, (prog, style) in enumerate(progs):
        cmds.append({"cmd": "load", "core": core, "bin": f"sw/{prog}/{prog}.bin"})
        if style == "external":
            cmds.append({"cmd": "clock", "core": core, "style": "external", "pin": clk_pin})
        else:
            cmds.append({"cmd": "clock", "core": core, "style": "fixed", "div_int": 1})
        start_cores.append(core)
    io = {}
    if args.edge == "fall":
        io["i_inv"] = 1 << clk_pin
    if args.sync_bypass:
        # data pins only; the clock must stay synchronised
        io["sync_bypass"] = sum(1 << p for p in lay["data"])
    if io:
        cmds.append({"cmd": "io_config", **io})
    cmds.append({"cmd": "start", "cores": start_cores})
    # Let the core reach its first wait before the waveform starts.
    cmds.append({"cmd": "run", "cycles": args.lead, "stop_on_trap": False})
    cmds.append({"cmd": "inject",
                 "events": [{"cycle": t, "pin": p, "value": v} for t, p, v in events]})
    chunk_cycles = round(args.chunk * args.period)
    total = round(n * args.period) + chunk_cycles
    done = 0
    while done < total:
        cmds.append({"cmd": "run", "cycles": chunk_cycles, "stop_on_trap": False})
        cmds.append({"cmd": "fifo_drain", "bank": bank})
        done += chunk_cycles
    cfg = {"fclk_mhz": args.fclk_mhz, "commands": cmds}
    if args.trace:
        cfg["trace"] = {"file": f"{args.name}.fst"}
    return cfg


def run_sim(args, cfg):
    sim = Path(args.sim).resolve()
    cfg_rel = f"configs/{args.name}.jsonc"
    (sim / cfg_rel).write_text(json.dumps(cfg, indent=1))
    # stdout and stderr go to separate files: the harness draws an unbuffered
    # progress bar on stderr that, if merged, lands in the middle of buffered
    # stdout lines and corrupts [fifo_drain] records.
    log = Path(args.logdir).resolve() / f"{args.name}.log"
    err = Path(args.logdir).resolve() / f"{args.name}.err.log"
    with open(log, "w") as fh, open(err, "w") as fe:
        rc = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{sim}:/work",
             "--user", f"{os.getuid()}:{os.getgid()}", args.image, cfg_rel],
            stdout=fh, stderr=fe).returncode
    return rc, log


def parse_words(log):
    words = []
    for line in log.read_text().splitlines():
        m = re.match(r"\[fifo_drain\]\s+\[\d+\] = 0x([0-9a-f]{8})", line)
        if m:
            words.append(int(m.group(1), 16))
    return words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", required=True)
    ap.add_argument("--logdir", required=True)
    ap.add_argument("--image", default="bio-sim")
    ap.add_argument("--mode", choices=sorted(MODES), default="single")
    ap.add_argument("--layout", choices=sorted(LAYOUTS), default="byte")
    ap.add_argument("--edge", choices=["rise", "fall"], default="rise")
    ap.add_argument("--period", type=float, default=28.0, help="project clock period in aclk cycles")
    ap.add_argument("--tco", type=int, default=2, help="data change delay after rising edge, aclk cycles")
    ap.add_argument("--clocks", type=int, default=480)
    ap.add_argument("--chunk", type=int, default=None,
                    help="project clocks between drains (default: 6 output words)")
    ap.add_argument("--lead", type=int, default=400)
    ap.add_argument("--fclk-mhz", type=float, default=700.0)
    ap.add_argument("--sync-bypass", action="store_true")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()
    if args.chunk is None:
        args.chunk = 6 * MODES[args.mode][2]
    if args.layout == "byte" and args.mode == "dual16":
        ap.error("dual16 packs BIO16-31 and needs --layout dabao")
    if args.layout == "dabao" and args.mode != "dual16":
        ap.error("the byte packers keep BIO0-7 only; use --mode dual16 with --layout dabao")
    if args.name is None:
        args.name = (f"ttcap-{args.mode}-{args.edge}-p{args.period:g}-tco{args.tco}"
                     + ("-sb" if args.sync_bypass else ""))

    rng = random.Random(args.seed)
    data = [rng.randrange(256) for _ in range(args.clocks)]
    cfg = build_config(args, data)
    rc, log = run_sim(args, cfg)
    words = parse_words(log)
    _, _, spw, bits, base = MODES[args.mode]
    lay = LAYOUTS[args.layout]
    got = []
    for w in words:
        for i in range(spw):
            sample = (w >> (bits * i)) & ((1 << bits) - 1)
            got.append(sum(((sample >> (pin - base)) & 1) << b
                           for b, pin in enumerate(lay["data"])))

    result = {"name": args.name, "rc": rc, "log": str(log), "words": len(words),
              "samples": len(got), "pixclk_mhz": round(args.fclk_mhz / args.period, 3)}
    # Find the start offset o such that got == seq[o:o+len(got)], where seq is
    # either data itself (each sample is the byte driven after its own edge:
    # "new") or data delayed by one edge (pins start at 0: "prev", i.e. the
    # read happened before tco). The core is already waiting when edge 0
    # arrives, so offset 0 is expected.
    match = None
    for phase, seq in (("new", data), ("prev", [0] + data)):
        for o in range(0, 64):
            if len(got) >= 0.8 * args.clocks and seq[o:o + len(got)] == got:
                match = (phase, o)
                break
        if match:
            break
    if match is not None:
        result.update(ok=True, phase=match[0], offset=match[1])
    else:
        # Best-effort diagnosis: the offset with most matches, and whether the
        # samples are the previous cycle's byte instead (late data window).
        best = max(range(0, 64),
                   key=lambda o: sum(a == b for a, b in zip(got, data[o:])))
        nmatch = sum(a == b for a, b in zip(got, data[best:]))
        first_bad = next((i for i, (a, b) in enumerate(zip(got, data[best:])) if a != b),
                         None)
        lo = max(0, (first_bad or 0) - 4)
        result.update(ok=False, best_offset=best, best_matches=nmatch,
                      first_bad=first_bad,
                      got_near_bad=[hex(x) for x in got[lo:lo + 10]],
                      expect_near_bad=[hex(x) for x in data[best + lo:best + lo + 10]])
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
