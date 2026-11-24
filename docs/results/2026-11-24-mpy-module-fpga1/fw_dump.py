import uctypes, ubinascii
FW_END = 0x100C8000
a = 0x10000000
while a < FW_END:
    k = min(3072, FW_END - a)
    print("B%08x %s" % (a, ubinascii.b2a_base64(bytes(uctypes.bytearray_at(a, k))).decode().strip()))
    a += k
print("END")
