#!/usr/bin/env python3
"""Compara i due cpio decompressi: entry per entry (campi header)."""
import gzip, sys

def entries(path):
    data = gzip.open(path, "rb").read()
    out = []
    pos = 0
    while pos < len(data) and data[pos:pos+6] in (b"070701", b"070702"):
        f = [int(data[pos+6+i*8: pos+6+(i+1)*8], 16) for i in range(13)]
        name = data[pos+110: pos+110+f[11]-1]
        fs = (pos + 110 + f[11] + 3) & ~3
        out.append((f, name, data[fs:fs+f[6]], pos, fs))
        pos = (fs + f[6] + 3) & ~3
        if name == b"TRAILER!!!":
            break
    return out, data

a, da = entries(sys.argv[1])
b, db = entries(sys.argv[2])
print(f"originale: {len(a)} entry, {len(da)} byte | mio: {len(b)} entry, {len(db)} byte")
for i, (ea, eb) in enumerate(zip(a, b)):
    fa, na, dda, pa, fsa = ea
    fb, nb, ddb, pb, fsb = eb
    ok_f = fa == fb or (na == b"first_stage_ramdisk/fstab.android-desktop")
    if not ok_f or na != nb or dda != ddb:
        print(f"[{i}] {na!r} vs {nb!r}")
        if fa != fb:
            print("   campi A:", [hex(x) for x in fa])
            print("   campi B:", [hex(x) for x in fb])
        if dda != ddb and len(dda) < 3000:
            print("   dati diversi")
        if na == nb and fa == fb and dda != ddb:
            print(f"   sizeA={len(dda)} sizeB={len(ddb)}")
print("prima entry orig:", a[0][1], "mio:", b[0][1])
print("ultima entry orig:", a[-1][1], "mio:", b[-1][1])
print("tail originale dopo trailer:", len(da) - (a[-1][4]), "byte")
print("tail mio:", len(db) - (b[-1][4]), "byte")
