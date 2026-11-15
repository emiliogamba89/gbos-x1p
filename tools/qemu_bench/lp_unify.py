#!/usr/bin/env python3
"""Uniforma TUTTI gli slot di metadata LP (primari + backup) al contenuto
dello slot 0 primario (@super+12288). Qualunque slot/copia liblp scelga,
vedra' il nostro layout (system_a 3 extent, vendor_a 3 extent).
Uso: lp_unify.py <raw>
"""
import struct, sys
from pathlib import Path

SECT = 512

def gpt(f):
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
    ss, _ = gpt(f)["super"]
    f.seek(ss + 4096)
    geo = f.read(4096)
    assert struct.unpack_from("<I", geo, 0)[0] == 0x616C4467, "geometry"
    meta_sz = struct.unpack_from("<I", geo, 40)[0]
    slots = struct.unpack_from("<I", geo, 44)[0]
    meta_base = 4096 * 3
    # slot 0 primario = la verita' corrente
    f.seek(ss + meta_base)
    truth = f.read(meta_sz)
    assert truth[:4] == b"0PLA", "slot0 primario senza magic"
    targets = []
    for slot in range(1, slots):
        targets.append(meta_base + slot * meta_sz)          # primari 1..n
    for copy in range(1, 4):
        base = meta_base + meta_sz * slots * copy
        for slot in range(slots):
            targets.append(base + slot * meta_sz)           # backup copie
    for off in targets:
        f.seek(ss + off)
        cur = f.read(meta_sz)
        if cur == truth:
            print(f"@{ss+off}: gia' identico")
            continue
        f.seek(ss + off)
        f.write(truth)
        print(f"@{ss+off}: sovrascritto con slot0 primario ({len(truth)} byte)")
    f.flush()
    import os
    os.fsync(f.fileno())
print("OK")
