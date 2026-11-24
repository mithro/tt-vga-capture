import os, sys, hashlib
print("uname", os.uname().release, os.uname().version)
try:
    print("sdk", tt.sdk_version)
except Exception as e:
    print("sdk ?", e)

def walk(d):
    for name in sorted(os.listdir(d)):
        p = (d.rstrip("/") + "/" + name) if d != "/" else "/" + name
        st = os.stat(p)
        if st[0] & 0x4000:
            walk(p)
        else:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while True:
                    b = f.read(1024)
                    if not b:
                        break
                    h.update(b)
            print("F", p, st[6], "".join("%02x" % x for x in h.digest()))

walk("/")
