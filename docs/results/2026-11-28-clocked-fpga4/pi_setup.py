"""Set up ~/tthfv-4d on fpga-4's Pi (setup), run hold_run there (run), or remove it (teardown).

usage: uv run --no-project python pi_setup.py setup|run|teardown   (logs to stdout; caller redirects)
"""

import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TT = Path.home() / "github/TinyTapeout"
ALIAS = "fpgas-welland-pi-sw2-p35"
CFG = str(Path.home() / ".config/fpgas-online/ssh_config")
SSH = ["ssh", "-F", CFG, "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15", ALIAS]
SCP = ["scp", "-q", "-F", CFG, "-o", "BatchMode=yes", "-o", "ConnectTimeout=20"]
TREE = TT / "vgacap-tthfv/.worktrees/clocked/python"
BIN = Path("BITSTREAMS/ttsky26c/tt_um_vga_ca/ttsky26c_vga_ca-c388675321d9.bin")
KK = Path("BITSTREAMS/ttsky26b/tt_um_KK_VGA01/ttsky26b_kk_vga01-7354ab9e6292.bin")
HELPER = TT / "tt-harness-fpga-vga/scripts/hardware_library/pi_helper.py"
D = "tthfv-4e"
COMMIT = "eb4ccb8"


def sh(args, timeout=120):
    print("$", " ".join(args), flush=True)
    rc = subprocess.run(args, timeout=timeout).returncode
    print(f"[exit {rc}]", flush=True)
    return rc


def setup() -> int:
    tar = HERE / "vgacap-python.tar"
    # from git at the reviewed commit, not the working tree (another agent may be editing it)
    if sh(["git", "-C", str(TREE.parent), "archive", "--format=tar", "--prefix=vgacap/", "-o", str(tar), COMMIT, "python"]):
        return 1
    rc = sh(SSH + ["ls -A ~; test ! -e tthfv-4e && mkdir tthfv-4e"])
    if rc:
        return rc
    for src in (tar, BIN, KK, HELPER, HERE / "clocked_batch.py", HERE.parent.parent / "d4/hw/ttcap_main.py"):
        dst = {BIN: "va.bin", KK: "kk.bin"}.get(src, src.name)
        if sh(SCP + [str(src), f"{ALIAS}:{D}/{dst}"]):
            return 1
    tar.unlink()
    return sh(SSH + [f"cd {D} && tar xf vgacap-python.tar && rm vgacap-python.tar && uv venv -q .venv"
                     " && uv pip install -q --python .venv/bin/python pyserial websockets && ls -A"], 300)


def update() -> int:
    """Replace the vgacap tree on the Pi with COMMIT's, and copy the current clocked_batch.py."""
    tar = HERE / "vgacap-python.tar"
    if sh(["git", "-C", str(TREE.parent), "archive", "--format=tar", "--prefix=vgacap/", "-o", str(tar), COMMIT, "python"]):
        return 1
    for src in (tar, HERE / "clocked_batch.py"):
        if sh(SCP + [str(src), f"{ALIAS}:{D}/{src.name}"]):
            return 1
    tar.unlink()
    return sh(SSH + [f"cd {D} && rm -rf vgacap && tar xf vgacap-python.tar && rm vgacap-python.tar && ls -A"
                     " && grep -n '^CLOCKED_SAMPLE_NS' vgacap/python/ttcap/capture.py"])


def run() -> int:
    rc = sh(SSH + [f"cd {D} && PYTHONPATH=vgacap/python PYTHONDONTWRITEBYTECODE=1 .venv/bin/python hold_run.py va.bin"],
            900)
    if sh(SSH + [f"test -s {D}/held.vgacap"]) == 0:
        sh(SCP + [f"{ALIAS}:{D}/held.vgacap", str(HERE / "held.vgacap")])
    return rc


def teardown() -> int:
    return sh(SSH + [f"rm -rf {D}; ls -A ~"])


def run_batch(batch: str) -> int:
    rc = sh(SSH + [f"cd {D} && PYTHONPATH=vgacap/python PYTHONDONTWRITEBYTECODE=1 .venv/bin/python clocked_batch.py {batch}"],
            1800)
    sh(SCP + [f"{ALIAS}:{D}/results_{batch}.json", str(HERE / f"results_{batch}.json")])
    sh(SSH + [f"cd {D} && ls -la *.vgacap"])
    sh(SCP + [f"{ALIAS}:{D}/{batch}_*.vgacap", str(HERE) + "/"], 600)
    return rc


if __name__ == "__main__":
    if sys.argv[1] == "batch":
        sys.exit(run_batch(sys.argv[2]))
    sys.exit({"setup": setup, "update": update, "teardown": teardown}[sys.argv[1]]())
