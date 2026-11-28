"""On fpga-4's Pi: one batch of 4e clocked-mode hardware runs, then restore the board.

usage (in ~/tthfv-4e): PYTHONPATH=vgacap/python PYTHONDONTWRITEBYTECODE=1 .venv/bin/python clocked_batch.py BATCH

BATCH is one of:
  a      N = 4 (R 1), 8 (R 1), 12 (R 10) at 500 kHz; then 3 runs of 4,194,304 clocks at 500 kHz (same samples?)
  b      H sweep: --clock-high 0..15, 400,000 clocks at 500 kHz (divider 14: every H reads >= 105 ns late)
  b2     H sweep at 7 MHz, divider 1: --clock-high 0..15, 400,000 clocks
  c      the fastest rate, 4,194,304 clocks; one run over the bridge (daemon up); a killed-host run
  kk     tt_um_KK_VGA01 (kk.bin), 4,194,304 clocks at 500 kHz and at the fastest rate

Each serial run is `ttcap capture serial:/dev/ttboard --mode clocked ...` with the daemon stopped
(pi_helper stop-if-idle, 0 clients). After every run the board's state is read over the raw REPL and
compared with the state before the batch: root listing, /_vgacap, tt.mode, the manual-clock monitor, rst_n.
At the end: restart_sdk, start fpgas-tt, wait for idle_display 'loaded'. Every step is logged; exit 0 only if
every run exited as expected, every post-state matched, and the board ended loaded.
"""

import json
import subprocess
import sys
import time

from ttcap.repl import RawRepl, SerialLink, restart_sdk

PY = sys.executable
PORT = "/dev/ttboard"
BIN = "va.bin"
RATE = 500000
BIG = 4194304

STATE = (
    "import os\n"
    "print(sorted(os.listdir('/')))\n"
    "print('_vgacap' in os.listdir('/'))\n"
    "print(tt.mode)\n"
    "m = getattr(tt, 'manual_project_clock', None)\n"
    "print(getattr(m, 'monitoring', 'n/a'))\n"
    "print(tt.rst_n())\n"
    "del m"
)


def run(args, timeout):
    print("$", " ".join(str(a) for a in args), flush=True)
    try:
        return subprocess.run([str(a) for a in args], timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        print(f"[timeout after {timeout} s]", flush=True)
        return 124


def state() -> list[str]:
    link = SerialLink(PORT)
    try:
        repl = RawRepl(link)
        repl.enter()
        out, err = repl.exec(STATE, timeout=10)
        if err.strip():
            return [f"error: {err.strip()}"]
        lines = out.strip().splitlines()
        return lines
    finally:
        link.close()


def sysclk() -> int:
    link = SerialLink(PORT)
    try:
        repl = RawRepl(link)
        repl.enter()
        out, err = repl.exec("import machine\nprint(machine.freq())", timeout=10)
        if err.strip():
            raise SystemExit(f"machine.freq() failed: {err.strip()}")
        return int(out.strip())
    finally:
        link.close()


def capture(out, clocks, extra=(), link=f"serial:{PORT}", rate=RATE, reset=None, timeout=300, bitstream=BIN):
    args = [PY, "ttcap_main.py", "capture", link, "--profile", "rp2350", "--mode", "clocked",
            "--bitstream", bitstream, "--clocks", clocks, "--clock-hz", rate, "--out", out]
    if reset is not None:
        args += ["--reset-clocks", reset]
    args += list(extra)
    t0 = time.monotonic()
    rc = run(args, timeout)
    print(f"[{out}: exit {rc} in {time.monotonic() - t0:.1f} s]", flush=True)
    return rc


def killed_host(out):
    """Start a 4 M-clock run, SIGKILL the host 12 s after start (about 5 s of load, then streaming), wait 40 s."""
    args = [PY, "ttcap_main.py", "capture", f"serial:{PORT}", "--profile", "rp2350", "--mode", "clocked",
            "--bitstream", BIN, "--clocks", BIG, "--clock-hz", RATE, "--out", out]
    print("$", " ".join(str(a) for a in args), "(SIGKILL after the load + 3 s)", flush=True)
    p = subprocess.Popen([str(a) for a in args])
    time.sleep(12)  # the load takes about 5 s; then 3+ s of streaming
    p.kill()
    p.wait()
    print(f"[killed, exit {p.returncode}; waiting 40 s for the board to finish the run]", flush=True)
    time.sleep(40)


def main() -> int:
    batch = sys.argv[1]
    rc = run([PY, "pi_helper.py", "stop-if-idle"], 60)
    if rc != 0:
        print(f"daemon not stopped (stop-if-idle exit {rc}); nothing done", flush=True)
        run(["sudo", "systemctl", "start", "fpgas-tt"], 60)
        return 2
    results = []
    ok = True
    try:
        before = state()
        print("state before:", before, flush=True)

        def check(label, rc, want_rc=0):
            nonlocal ok
            after = state()
            same = len(after) >= 5 and len(before) >= 5 and after[:4] == before[:4]
            # rst_n (line 5): after a run it must be released, reading 1.
            released = len(after) >= 5 and after[4] == "1"
            good = rc == want_rc and same and released
            ok &= good
            results.append({"run": label, "exit": rc, "want_exit": want_rc, "state": after, "same": same,
                            "rst_n_released": released, "ok": good})
            print(f"post-state {label}: {after} same={same} rst_n_released={released} ok={good}", flush=True)

        if batch == "a":
            for n, r in ((4, 1), (8, 1), (12, 10)):
                check(f"n{n}", capture(f"a_n{n}.vgacap", n, reset=r))
            for i in range(3):
                check(f"big{i}", capture(f"a_big{i}.vgacap", BIG))
        elif batch == "b":
            for h in range(16):
                check(f"h{h}", capture(f"b_h{h:02d}.vgacap", 400000, extra=("--clock-high", h)))
        elif batch == "b2":
            # divider 1: H steps of one sysclk (7.5 ns at 133 MHz), read (H+1) cycles after the edge
            for h in range(16):
                check(f"h{h}", capture(f"b2_h{h:02d}.vgacap", 400000, rate=7000000, extra=("--clock-high", h)))
        elif batch == "c":
            # the fastest under the 80 ns floor at divider 1 is sysclk / 14 (H 10, L 0, for sysclk up to
            # about 137 MHz); ask for ceil(F) Hz, which the host makes as exactly F
            hz = sysclk()
            fast = -(-hz // 14)
            print(f"sysclk {hz} Hz: asking for the fastest clock, {fast} Hz", flush=True)
            check("max", capture("c_max.vgacap", BIG, rate=fast))
            killed_host("c_killed.vgacap")
            check("killed", 0)
            # the bridge run: daemon up, through its WebSocket on localhost
            run(["sudo", "systemctl", "start", "fpgas-tt"], 60)
            run([PY, "pi_helper.py", "wait-loaded", "170"], 200)
            rcb = capture("c_bridge.vgacap", BIG, link="ws://127.0.0.1:8765/serial")
            rc = run([PY, "pi_helper.py", "stop-if-idle"], 60)
            if rc != 0:
                print("could not stop the daemon after the bridge run (a visitor?)", flush=True)
                ok = False
            else:
                check("bridge", rcb)
        elif batch == "kk":
            # issue #73's design: its game state resets only on a vsync edge during reset, so only a held load
            # and a clocked start from reset can reset it
            hz = sysclk()
            check("kk500k", capture("kk_500k.vgacap", BIG, bitstream="kk.bin"))
            check("kkmax", capture("kk_max.vgacap", BIG, rate=-(-hz // 14), bitstream="kk.bin"))
        else:
            raise SystemExit(f"unknown batch {batch!r}")
    finally:
        link = SerialLink(PORT)
        try:
            okr, text = restart_sdk(link)
            print(f"restart_sdk ok={okr}", flush=True)
            print(text[-300:], flush=True)
        finally:
            link.close()
        start = run(["sudo", "systemctl", "start", "fpgas-tt"], 60)
        loaded = run([PY, "pi_helper.py", "wait-loaded", "170"], 200)
        print(f"start exit {start}, wait-loaded exit {loaded}", flush=True)
        with open(f"results_{batch}.json", "w") as f:
            json.dump(results, f, indent=1)
    # wait-loaded exit 6: a visitor took the board after the restart (idle_display 'in use'), not a fault
    good = ok and okr and loaded in (0, 6)
    print("RESULT", "PASS" if good else "FAIL", flush=True)
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
