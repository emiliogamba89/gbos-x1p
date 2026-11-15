#!/usr/bin/env python3
"""Aggiunge una extent AGGIUNTIVA a system_a (terza+) senza il ramo
idempotente di extend_system_lp.extend_partition: serve quando l'extent
extra esistente non basta piu'. Uso: grow_system_lp.py <raw> <extra_bytes>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extend_system_lp import (SECT, gpt_partitions, lp_extents,
                              extend_partition)


def add_extra_extent(raw, part_name, extra_bytes):
    raw = Path(raw)
    super_start, super_end = gpt_partitions(raw)["super"]
    super_sectors = (super_end - super_start) // SECT
    with open(raw, "r+b") as f:
        f.seek(super_start + 12288)
        m = bytearray(f.read(65536))
    u = lambda b, o: __import__("struct").unpack_from("<I", b, o)[0]
    import struct
    hs = u(m, 8)
    tables = bytes(m[hs:hs + u(m, 44)])
    ps, pc, psz = struct.unpack_from("<III", m, 80)
    es, ec, esz = struct.unpack_from("<III", m, 92)
    parts = [tables[ps + i * psz: ps + (i + 1) * psz] for i in range(pc)]
    exts = [struct.unpack("<QIQI", tables[es + j * esz: es + (j + 1) * esz])
            for j in range(ec)]
    si = next(i for i, p in enumerate(parts)
              if p[:36].split(b"\0")[0].decode() == part_name)
    att, fei, num, grp = struct.unpack_from("<IIII", parts[si], 36)
    deficit = (extra_bytes + SECT - 1) // SECT
    all_ends = [e[2] + e[0] for e in exts if e[0]]
    gap = (max(all_ends) + 7) & ~7
    end_lim = super_sectors - 256
    assert gap + deficit <= end_lim, "spazio insufficiente nel super"
    last = exts[fei + num - 1]
    new_ext = (deficit, last[1], gap, last[3])
    exts = exts[:fei + num] + [new_ext] + exts[fei + num:]
    for j in range(len(parts)):
        a2, f2, n2, g2 = struct.unpack_from("<IIII", parts[j], 36)
        if j == si:
            n2 = num + 1
        elif f2 > fei:
            f2 += 1
        parts[j] = parts[j][:36] + struct.pack("<IIII", a2, f2, n2, g2)
    pb = b"".join(parts)
    eb = b"".join(struct.pack("<QIQI", *e) for e in exts)
    import hashlib
    gs, gc, gsz = struct.unpack_from("<III", m, 104)
    ds, dc, dsz = struct.unpack_from("<III", m, 116)
    groups = tables[gs:gs + gc * gsz]
    devices = tables[ds:ds + dc * dsz]
    nb = pb + eb + groups + devices
    m2 = bytearray(m)
    m2[44:48] = struct.pack("<I", len(nb))
    m2[48:80] = hashlib.sha256(nb).digest()
    m2[hs:hs + len(nb)] = nb
    for o, d in ((80, (0, pc, psz)), (92, (len(pb), len(exts), esz)),
                 (104, (len(pb) + len(eb), gc, gsz)),
                 (116, (len(pb) + len(eb) + len(groups), dc, dsz))):
        struct.pack_into("<III", m2, o, *d)
    m2[12:44] = hashlib.sha256(bytes(m2[:12]) + bytes(32) + bytes(m2[44:hs])).digest()
    with open(raw, "r+b") as f:
        f.seek(super_start + 12288)
        f.write(m2)
    off2 = super_start + gap * SECT
    print(f"[LP] {part_name} +1 extent: {deficit} settori @rel {gap} (abs {off2})")
    return off2, deficit * SECT


if __name__ == "__main__":
    raw, extra = sys.argv[1], int(sys.argv[2])
    off, size = add_extra_extent(raw, "system_a", extra)
    ext = lp_extents(raw, "system_a")
    print(json.dumps({"extents": ext, "new": [off, size]}))
