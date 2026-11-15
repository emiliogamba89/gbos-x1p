#!/usr/bin/env python3
"""Analizza e ripara i metadati LP del super dopo l'estensione di system_a:
- stampa extents e groups
- aggiorna il maximum_size del group default (liblp rifiuta una extent list
  che eccede il max del gruppo: "Logical partition has invalid extent list")
"""
import hashlib, struct
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent.parent / "downloads/mica-16471258/disk-writable.raw"
SECT = 512

def crc32c(data):
    crc = 0xffffffff
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82f63b78 if crc & 1 else 0)
    return crc ^ 0xffffffff

def main():
    with RAW.open("rb") as f:
        f.seek(512)
        h = f.read(92)
        ent_lba, n, esz = struct.unpack_from("<QII", h, 72)
        f.seek(ent_lba * SECT)
        entries = f.read(n * esz)
    s_first = None
    for i in range(n):
        e = entries[i * esz:(i + 1) * esz]
        if e[:16] == b"\x00" * 16:
            continue
        name = e[56:128].decode("utf-16-le").rstrip("\x00")
        first, last = struct.unpack_from("<QQ", e, 32)
        if name == "super":
            s_first = first
    super_start = s_first * SECT

    with RAW.open("r+b") as f:
        f.seek(super_start + 12288)
        m = bytearray(f.read(65536))
    hs = struct.unpack_from("<I", m, 8)[0]
    tsz = struct.unpack_from("<I", m, 44)[0]
    tables = bytes(m[hs:hs + tsz])
    ps, pc, psz = struct.unpack_from("<III", m, 80)
    es, ec, esz_l = struct.unpack_from("<III", m, 92)
    gs, gc, gsz = struct.unpack_from("<III", m, 104)

    parts = [tables[ps + i * psz: ps + (i + 1) * psz] for i in range(pc)]
    exts = [struct.unpack("<QIQI", tables[es + j * esz_l: es + (j + 1) * esz_l])
            for j in range(ec)]
    print("PARTITIONS:")
    for p in parts:
        nm = p[:36].split(b"\0")[0].decode()
        a2, f2, n2, g2 = struct.unpack_from("<IIII", p, 36)
        if n2:
            print(f"  {nm:14s} first={f2} num={n2}")
    print("EXTENTS:")
    used_max = 0
    for j, e in enumerate(exts):
        if e[0] == 0:
            continue
        abs_start = super_start + e[2] * SECT
        abs_end = abs_start + e[0] * SECT
        used_max = max(used_max, abs_end)
        print(f"  [{j}] sect={e[0]} rel={e[2]} abs={abs_start}..{abs_end}")
    print(f"super_start={super_start} used_max={used_max}")

    print("GROUPS:")
    gtab_off = gs
    new_groups = bytearray()
    for gi in range(gc):
        g = tables[gtab_off + gi * gsz: gtab_off + (gi + 1) * gsz]
        gname = g[:36].split(b"\0")[0].decode()
        gflags = struct.unpack_from("<I", g, 36)[0]
        gmax = struct.unpack_from("<Q", g, 40)[0]
        usage = sum(e[0] * SECT for e in exts)
        # il max del gruppo e' relativo all'inizio del super
        new_max = max(gmax, used_max - super_start + (256 << 20))
        print(f"  {gname}: flags={gflags} max={gmax} ({gmax>>20} MiB) "
              f"-> new_max={new_max} ({new_max>>20} MiB) uso_attuale={usage>>20} MiB")
        ng = bytearray(g)
        struct.pack_into("<Q", ng, 40, new_max)
        new_groups += ng

    pb = b"".join(parts)
    eb = b"".join(struct.pack("<QIQI", *e) for e in exts)
    ds, dc, dsz = struct.unpack_from("<III", m, 116)
    devices = tables[ds:ds + dc * dsz]
    nb = pb + eb + bytes(new_groups) + devices
    struct.pack_into("<I", m, 44, len(nb))
    m[48:80] = hashlib.sha256(nb).digest()
    m[hs:hs + len(nb)] = nb
    m[12:44] = hashlib.sha256(bytes(m[:12]) + bytes(32) + bytes(m[44:hs])).digest()
    with RAW.open("r+b") as f:
        f.seek(super_start + 12288)
        f.write(m)
    print("[OK] metadata LP riscritti con group maximum_size aggiornato")

if __name__ == "__main__":
    main()
