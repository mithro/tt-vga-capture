# SPDX-License-Identifier: Apache-2.0
"""List processes this project's work may have left running, with how long
they have run, their state and CPU, so a stuck or orphaned one stands out.

    uv run --no-project python tools/bg_health.py

Read-only. It reads `ps fax`-style data (every process, with its parent) and
reports EVERY descendant of this session's claude process -- shells,
wrappers, sub-agents' work, anything -- plus orphans of this project's own
tools. No keyword list decides what is ours: on 2026-11-24 the old one
reported "nothing running" while a CI watcher and a sub-agent's 59
simulator containers were. A big batch is summarised by command, with each
flagged process still listed on its own. Flags:

* STUCK?   in D state, or a watcher/tunnel older than its expected life;
* ORPHAN?  re-parented to init (ppid 1) or to a systemd --user manager;
* ZOMBIE   state Z.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess

#: Longest a process of each kind should live before it is worth a look.
EXPECTED_S = {"watch_ci": 1900, "watch_hil": 1600, "hil.py": 1800, "pytest": 1800,
              "gst-launch": 1800, "ttcap": 1800, "hil_stub": 600, "fake_ttcap": 600,
              "tweed.welland": 6 * 3600}


#: Orphans only this project leaves behind: worth flagging whoever started them.
OURS_IF_ORPHANED = re.compile(r"hil_stub_ttcap|fake_ttcap|vgacapttsrc|tools/hil\.py|"
                              r"L 180\d\d:10\.21\.2\.\d+:8765")


def session_root() -> int:
    """The Claude process this check runs under: everything it started is ours."""
    pid = os.getppid()
    while pid > 1:
        stat = pathlib.Path(f"/proc/{pid}/stat").read_text()
        cmd = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        if re.search(r"(^|/)claude( |$)", cmd):
            return pid
        pid = int(stat.rsplit(")", 1)[1].split()[1])
    return 1


def main() -> int:
    out = subprocess.run(["ps", "-eo", "pid,ppid,stat,etimes,pcpu,args"],
                         capture_output=True, text=True, check=True).stdout.splitlines()
    user_managers = {line.split()[0] for line in out[1:] if "systemd --user" in line}
    parent = {f.split()[0]: f.split()[1] for f in out[1:] if len(f.split()) > 1}
    root = str(session_root())

    def ours(pid: str) -> bool:
        while pid in parent and pid not in ("0", "1"):
            if pid == root:
                return True
            pid = parent[pid]
        return False

    me = str(os.getpid())
    rows = []
    for line in out[1:]:
        fields = line.split(None, 5)
        if len(fields) < 6:
            continue
        pid, ppid, stat, etimes, pcpu, args = fields
        if pid in (me, root) or parent.get(me) == pid or "bg_health.py" in args:
            continue  # this check itself, and the claude process
        orphan = ppid == "1" or ppid in user_managers
        if not ours(pid) and not (orphan and OURS_IF_ORPHANED.search(args)):
            continue
        flags = []
        if stat.startswith("Z"):
            flags.append("ZOMBIE")
        if stat.startswith("D"):
            flags.append("STUCK? (D state)")
        if orphan:
            flags.append("ORPHAN?")
        for key, limit in EXPECTED_S.items():
            if key in args and int(etimes) > limit:
                flags.append(f"STUCK? (running {int(etimes)//60} min, expected < {limit//60})")
                break
        rows.append((pid, ppid, stat, int(etimes), pcpu, args.strip()[:150], flags))
    if not rows:
        print(f"OK: no project background processes running (session root pid {root})")
        return 0
    bad = [r for r in rows if r[6]]
    print(f"{len(rows)} process(es) of this session, {len(bad)} flagged")
    groups: dict[str, list] = {}
    for row in rows:
        words = [w for w in row[5].split() if not w.startswith("-")]
        key = " ".join(pathlib.Path(w).name for w in words[:2])
        groups.setdefault(key, []).append(row)
    for key, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        oldest = max(m[3] for m in members)
        cpu = sum(float(m[4]) for m in members)
        print(f"  {len(members):>4} x {key[:70]:<70} oldest {oldest//60:>4} min, {cpu:5.1f}% cpu")
    for pid, ppid, stat, et, cpu, args, flags in rows:
        if flags:
            print(f"  {pid:>7} ppid {ppid:>7} {stat:<5} {et//60:>5} min {cpu:>5}%  {args}"
                  f" <-- {'; '.join(flags)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
