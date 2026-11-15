#!/usr/bin/env python3
"""Analizza TUTTI gli slot di metadati LP del super (primari e backup):
per ognuno stampa validita' (magic/header-sha), slot_sequence, tables_size
e la mappa extents di system_a. Cosi' si vede quale slot init potra' scegliere.
"""
import hashlib, struct, sys

raw = sys.argv[1] if len(sys.argv) > 1 else "/home/zero89/disk-run.raw"
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

f = open(raw, "rb")
ss, se = gpt(f)["super"]
print(f"super: {ss}..{se} ({(se-ss)//512} settori)")

f.seek(ss + 4096)
geo = f.read(4096)
assert struct.unpack_from("<I", geo, 0)[0] == 0x616C4467, f"geometry magic {geo[:4]!r}"
meta_sz, meta_slots = struct.unpack_from("<II", geo, 40)
print(f"geometry: metadata_max_size={meta_sz} slots={meta_slots}")

# primary @ 4096*3; le copie backup seguono subito dopo l'area primaria
meta_base = 4096 * 3
areas = [(meta_base, "primary")]
for i in range(1, 4):
    areas.append((meta_base + meta_sz * meta_slots * i, f"backup{i}"))

for base, label in areas:
    for slot in range(meta_slots):
        off = ss + base + slot * meta_sz
        f.seek(off)
        m = f.read(meta_sz)
        if m[:4] != b"0PLA":
            print(f"{label} slot{slot} @{off}: NO MAGIC ({m[:4]!r})")
            continue
        hs = struct.unpack_from("<I", m, 8)[0]
        tsz = struct.unpack_from("<I", m, 44)[0]
        ok_hdr = hashlib.sha256(m[:12] + bytes(32) + m[44:hs]).digest() == m[12:44]
        tables = m[hs:hs + tsz]
        ok_tab = hashlib.sha256(tables).digest() == m[48:80]
        # extents di system_a
        ps, pc, psz = struct.unpack_from("<III", m, 80)
        es, ec, esz = struct.unpack_from("<III", m, 92)
        exts = [struct.unpack_from("<QIQI", tables[es + j * esz: es + (j + 1) * esz]) for j in range(ec)]
        sysinfo = ""
        for i in range(pc):
            p = tables[ps + i * psz: ps + (i + 1) * psz]
            nm = p[:36].split(b"\0")[0].decode()
            if nm in ("system_a", "system_b"):
                _, fei, num, _ = struct.unpack_from("<IIII", p, 36)
                tot = sum(exts[fei + k][0] * SECT for k in range(num))
                sysinfo += f" {nm}={num}ext/{tot}B"
        print(f"{label} slot{slot} @{off}: magic OK hdr_sha={ok_hdr} tab_sha={ok_tab} tsz={tsz}{sysinfo}")
