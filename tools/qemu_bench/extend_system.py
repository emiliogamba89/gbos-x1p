#!/usr/bin/env python3
"""Aggiunge un extent a system_a nei metadati LP del super (la partizione
system cresce nella zona NON allocata tra la sua fine e vendor_a ~5.65GB).
Serve perche' mkfs.erofs --incremental non libera i blocchi dei file
sostituiti: l'immagine con services.jar patchato cresce di ~22MB.
Uso: python3 extend_system.py [--add-mb 24]
"""
import hashlib, struct, sys
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent.parent / "downloads/mica-16471258/disk-writable.raw"
SECT = 512

def crc(data):
    import zlib
    return zlib.crc32(data) & 0xFFFFFFFF

def header_crc(h):
    struct.pack_into("<I", h, 88 - 84 + 0 if False else 32, 0)  # placeholder

def main():
    add_mb = 24
    if len(sys.argv) > 2 and sys.argv[1] == "--add-mb":
        add_mb = int(sys.argv[2])
    with RAW.open("rb") as f:
        f.seek(512)
        h = f.read(92)
        ent_lba, n, esz = struct.unpack_from("<QII", h, 72)
        f.seek(ent_lba * SECT)
        entries = f.read(n * esz)
    # super partition
    s_first = s_last = None
    for i in range(n):
        e = entries[i * esz:(i + 1) * esz]
        if e[:16] == b"\x00" * 16:
            continue
        name = e[56:128].decode("utf-16-le").rstrip("\x00")
        first, last = struct.unpack_from("<QQ", e, 32)
        if name == "super":
            s_first, s_last = first, last
    assert s_first is not None, "super non trovata"
    super_start = s_first * SECT

    with RAW.open("r+b") as f:
        f.seek(super_start + 12288)
        m = bytearray(f.read(65536))
    hs = struct.unpack_from("<I", m, 8)[0]
    tsz = struct.unpack_from("<I", m, 44)[0]
    tables = bytes(m[hs:hs + tsz])
    ps, pc, psz = struct.unpack_from("<III", m, 80)
    es, ec, esz_l = struct.unpack_from("<III", m, 92)

    parts = [tables[ps + i * psz: ps + (i + 1) * psz] for i in range(pc)]
    exts = [struct.unpack("<QIQI", tables[es + j * esz_l: es + (j + 1) * esz_l])
            for j in range(ec)]

    si = next(i for i, p in enumerate(parts)
              if p[:36].split(b"\0")[0] == b"system_a")
    att, fei, num, grp = struct.unpack_from("<IIII", parts[si], 36)
    vend = exts[fei:fei + num]
    last_end_abs = super_start + max(e[2] * SECT + e[0] * SECT for e in vend)
    print(f"system_a: {num} extents, fine fisica {last_end_abs}")

    new_abs = (last_end_abs + 4095) & ~4095
    add_sectors = add_mb * 1024 * 1024 // SECT
    rel = (new_abs - super_start) // SECT
    print(f"nuova extent: abs {new_abs} rel {rel} (+{add_sectors} settori = {add_mb} MiB)")

    # IDEMPOTENTE: la lista di system_a e' sempre [extent_originale, extent_extra]
    # (se un run precedente ne aveva aggiunta una, la rimpiazzo con offset corretto)
    # NB: la zona libera vera inizia DOPO le micro-extents del vendor
    # (@1258655744/1258659840/1258663936), quindi calcolo la fine di TUTTE
    # le extents esistenti
    all_ends = [super_start + e[2] * SECT + e[0] * SECT for e in exts if e[0]]
    free_abs = (max(all_ends) + 4095) & ~4095
    rel = (free_abs - super_start) // SECT
    print(f"zona libera da abs {free_abs} rel {rel}")
    if len(vend) >= 2 and vend[1][2] == rel:
        print("extent extra gia' presente con offset corretto: rimpiazzo solo la size")
        sys_exts = [vend[0], (add_sectors, 0, rel, 0)]
        exts = exts[:fei] + sys_exts + exts[fei + num:]
    else:
        sys_exts = [vend[0], (add_sectors, 0, rel, 0)]
        delta = len(sys_exts) - num
        exts = exts[:fei] + sys_exts + exts[fei + num:]
        for j in range(len(parts)):
            a2, f2, n2, g2 = struct.unpack_from("<IIII", parts[j], 36)
            if j == si:
                n2 = len(sys_exts)
            elif f2 > fei:
                f2 += delta
            parts[j] = parts[j][:36] + struct.pack("<IIII", a2, f2, n2, g2)
    pb = b"".join(parts)
    eb = b"".join(struct.pack("<QIQI", *e) for e in exts)
    gs, gc, gsz = struct.unpack_from("<III", m, 104)
    ds, dc, dsz = struct.unpack_from("<III", m, 116)
    groups = tables[gs:gs + gc * gsz]
    devices = tables[ds:ds + dc * dsz]
    nb = pb + eb + groups + devices
    struct.pack_into("<I", m, 44, len(nb))
    m[48:80] = hashlib.sha256(nb).digest()
    m[hs:hs + len(nb)] = nb
    m[12:44] = hashlib.sha256(bytes(m[:12]) + bytes(32) + bytes(m[44:hs])).digest()
    with RAW.open("r+b") as f:
        f.seek(super_start + 12288)
        f.write(m)
    print(f"[OK] system_a estesa: {num} -> {len(sys_exts)} extents; "
          f"nuova extent @abs {new_abs} ({add_mb} MiB). "
          f"Scriverai l'immagine spezzata: {SYSTEM_SIZE if False else 1081446400} + resto")

if __name__ == "__main__":
    main()
