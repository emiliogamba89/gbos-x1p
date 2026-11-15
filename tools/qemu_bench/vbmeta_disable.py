#!/usr/bin/env python3
"""Imposta flags=3 (VERIFICATION_DISABLED | HASHTREE_DISABLED) nell'header
AVB0 di TUTTE le partizioni vbmeta_* della GPT. Con questi flag libavb non
costruisce la tabella dm-verity/FEC e /system viene servita dai byte reali
del disco (le nostre patch!). Le firme non contano: col flag la verifica
viene saltata del tutto (e il device e' unlocked/orange comunque).
Uso: vbmeta_disable.py <raw>
"""
import struct, sys
from pathlib import Path

SECT = 512
FLAGS_OFF = 120  # avb_vbmeta_image_header.flags (uint64 LE)

def gpt_parts(f):
    f.seek(512)
    h = f.read(92)
    ent_lba, num, esz = struct.unpack_from("<QII", h, 72)
    out = {}
    for i in range(num):
        f.seek(ent_lba * SECT + i * esz)
        e = f.read(esz)
        if e[:16] == bytes(16):
            continue
        name = e[56:128].decode("utf-16-le").split("\0")[0]
        first, last = struct.unpack_from("<QQ", e, 32)
        out[name] = (first * SECT, (last + 1) * SECT)
    return out

raw = Path(sys.argv[1])
with open(raw, "r+b") as f:
    for name, (start, end) in sorted(gpt_parts(f).items()):
        if not name.startswith("vbmeta"):
            continue
        f.seek(start)
        magic = f.read(4)
        if magic != b"AVB0":
            print(f"{name}: niente AVB0 ({magic!r}), salto")
            continue
        f.seek(start + FLAGS_OFF)
        old = struct.unpack("<Q", f.read(8))[0]
        f.seek(start + FLAGS_OFF)
        f.write(struct.pack("<Q", 3))
        print(f"{name} @{start}: flags {old} -> 3 (verify+hashtree disabled)")
    f.flush()
    import os
    os.fsync(f.fileno())
print("OK")
