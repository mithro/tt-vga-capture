import os, ubinascii

def walk(d):
    for name in sorted(os.listdir(d)):
        p = (d.rstrip("/") + "/" + name) if d != "/" else "/" + name
        if os.stat(p)[0] & 0x4000:
            print("D " + p)
            walk(p)
        else:
            print("F " + p)
            with open(p, "rb") as f:
                while True:
                    b = f.read(1536)
                    if not b:
                        break
                    print("C " + ubinascii.b2a_base64(b).decode().strip())
            print("E")

walk("/")
print("END")
