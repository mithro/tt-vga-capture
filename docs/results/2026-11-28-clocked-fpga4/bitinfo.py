"""Print each file's size in bytes and its sha256.

usage (in BITSTREAMS): python bitinfo.py FILE.bin ...
"""
import hashlib, sys
from pathlib import Path
for p in sys.argv[1:]:
    b = Path(p).read_bytes()
    print(f"{p}: {len(b)} bytes, sha256 {hashlib.sha256(b).hexdigest()}")
