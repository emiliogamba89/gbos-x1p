#!/usr/bin/env python3
"""Estende una partizione logica (default system_a) nei metadati LP del super,
con lo STESSO algoritmo collaudato di vendor_port.expand_vendor_lp:
  - inserisce la nuova extent subito dopo quelle della partizione
  - shifta i first_extent_index delle partizioni successive
  - ricalcola tables_size @44, sha256(tabelle) @48 e il digest sha256 del
    header nel formato LP nuovo (sha256(header[0:12]||32x0||header[44:hs]))
  - scrive solo lo slot 0 primario @super+12288 (come fa il vendor: e' quello
    che init legge al boot)
Uso: python3 extend_system_lp.py <raw> <partizione> <extra_bytes>
Ritorna (stampa) offset assoluto e dimensione della nuova extent.
"""
import hashlib, json, struct, sys
from pathlib import Path

SECT = 512


def gpt_partitions(raw):
    with open(raw, "rb") as f:
        f.seek(512)
        h = f.read(92)
        assert h[:8] == b"EFI PART", "header GPT"
        ent_lba, num_ents, ent_size = struct.unpack_from("<QII", h, 72)
        out = {}
        for i in range(num_ents):
            f.seek(ent_lba * SECT + i * ent_size)
            e = f.read(ent_size)
            if e[:16] == bytes(16):
                continue
            name = e[56:128].decode("utf-16-le").split("\0")[0]
            first, last = struct.unpack_from("<QQ", e, 32)
            out[name] = (first * SECT, (last + 1) * SECT)
        return out


def lp_extents(raw, part_name):
    """[(offset_assoluto, bytes)] delle extent della partizione (LP slot 0)."""
    super_start, _ = gpt_partitions(raw)["super"]
    with open(raw, "rb") as f:
        f.seek(super_start + 12288)
        m = f.read(65536)
    u = lambda b, o: struct.unpack_from("<I", b, o)[0]
    hs = u(m, 8)
    tables = m[hs:hs + u(m, 44)]
    ps, pc, psz = struct.unpack_from("<III", m, 80)
    es, ec, esz = struct.unpack_from("<III", m, 92)
    all_ext = [struct.unpack_from("<QIQI", tables[es + j * esz: es + (j + 1) * esz])
               for j in range(ec)]
    for i in range(pc):
        p = tables[ps + i * psz: ps + (i + 1) * psz]
        if p[:36].split(b"\0")[0].decode() == part_name:
            _, fei, num, _ = struct.unpack_from("<IIII", p, 36)
            return [(super_start + all_ext[fei + k][2] * SECT,
                     all_ext[fei + k][0] * SECT) for k in range(num)]
    raise SystemExit(f"{part_name} non trovata")


def extend_partition(raw, part_name, extra_bytes):
    """Aggiunge una extent di extra_bytes a part_name. Idempotente: se la
    partizione ha gia' una extent extra con la stessa size, non fa nulla."""
    raw = Path(raw)
    super_start, super_end = gpt_partitions(raw)["super"]
    super_sectors = (super_end - super_start) // SECT
    with open(raw, "r+b") as f:
        f.seek(super_start + 12288)
        m = bytearray(f.read(65536))
    u = lambda b, o: struct.unpack_from("<I", b, o)[0]
    hs = u(m, 8)
    tsz = u(m, 44)
    tables = bytes(m[hs:hs + tsz])
    ps, pc, psz = struct.unpack_from("<III", m, 80)
    es, ec, esz = struct.unpack_from("<III", m, 92)
    parts = [tables[ps + i * psz: ps + (i + 1) * psz] for i in range(pc)]
    exts = [struct.unpack("<QIQI", tables[es + j * esz: es + (j + 1) * esz])
            for j in range(ec)]
    si = next(i for i, p in enumerate(parts)
              if p[:36].split(b"\0")[0].decode() == part_name)
    att, fei, num, grp = struct.unpack_from("<IIII", parts[si], 36)
    cur = exts[fei:fei + num]
    deficit = (extra_bytes + SECT - 1) // SECT

    # gap: coda del super dopo TUTTE le extent esistenti, allineata a 4096
    all_ends = [e[2] + e[0] for e in exts if e[0]]
    gap = (max(all_ends) + 7) & ~7          # settore relativo, allineato 4KiB
    end_lim = super_sectors - 256           # riserva backup metadata
    assert gap + deficit <= end_lim, "spazio insufficiente nel super"

    if num >= 2 and cur[-1][0] >= deficit:
        print(f"[LP] {part_name} ha gia' l'extent extra ({cur[-1][0]} settori @rel {cur[-1][2]})")
        return super_start + cur[-1][2] * SECT, cur[-1][0] * SECT

    last = cur[-1]
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
    raw, pname, extra = sys.argv[1], sys.argv[2], int(sys.argv[3])
    off, size = extend_partition(raw, pname, extra)
    ext = lp_extents(raw, pname)
    print(json.dumps({"extents": ext, "new": [off, size]}))
