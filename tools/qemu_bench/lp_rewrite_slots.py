#!/usr/bin/env python3
"""Riscrive i metadati LP corretti in ENTRAMBI gli slot (primario @12288 e
backup in fondo al super) con il CRC32C del blocco metadata calcolato
in modo corretto. Senza CRC32C valido liblp scarta il primario e il
first-stage init muore in "partition(s) not found".
Il contenuto = la disposizione canonica di lp_rebuild.py (13 extents).
"""
import hashlib, struct
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent.parent / "downloads/mica-16471258/disk-writable.raw"
SECT = 512

EXTENTS = [
    (2112200, 2048), (49152, 15815496),
    (8569832, 2115584),
    (753808, 10686464), (43992, 15699896),
    (8, 2114248), (8, 2114256), (16, 2114264), (71608, 15743888),
    (3847672, 11442176), (357200, 15290368), (16568, 15648768),
    (32768, 15667200),
]
PARTITIONS = {
    "system_a": (0, 2), "system_b": (2, 1), "vendor_a": (3, 6),
    "product_a": (9, 1), "system_ext_a": (10, 1),
    "system_dlkm_a": (11, 1), "vendor_dlkm_a": (12, 1),
}
GROUP_MAX = 16 * 1024 * 1024 * 1024

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
    s_first = s_last = None
    for i in range(n):
        e = entries[i * esz:(i + 1) * esz]
        if e[:16] == b"\x00" * 16:
            continue
        name = e[56:128].decode("utf-16-le").rstrip("\x00")
        first, last = struct.unpack_from("<QQ", e, 32)
        if name == "super":
            s_first, s_last = first, last
    super_start = s_first * SECT
    super_size = (s_last - s_first + 1) * SECT
    print(f"super: start={super_start} size={super_size} ({super_size>>20} MiB)")

    # geometry @4096: checksum, metadata_max_size, metadata_slot_count, logical_block_size
    with RAW.open("rb") as f:
        f.seek(super_start + 4096)
        geo = f.read(64)
    assert struct.unpack_from("<I", geo, 0)[0] == 0x616c4467, "magic geometry LP"
    meta_max = struct.unpack_from("<I", geo, 4)[0]
    slot_count = struct.unpack_from("<I", geo, 8)[0]
    print(f"geometry: metadata_max_size={meta_max} slot_count={slot_count}")

    # leggi il primario (slot 0) e ricostruisci il contenuto canonico
    with RAW.open("rb") as f:
        f.seek(super_start + 12288)
        m = bytearray(f.read(meta_max))
    hs = struct.unpack_from("<I", m, 8)[0]
    tables = bytes(m[hs:hs + struct.unpack_from("<I", m, 44)[0]])
    ps, pc, psz = struct.unpack_from("<III", m, 80)
    es, ec, esz_l = struct.unpack_from("<III", m, 92)
    gs, gc, gsz = struct.unpack_from("<III", m, 104)
    ds, dc, dsz = struct.unpack_from("<III", m, 116)
    parts = [tables[ps + i * psz: ps + (i + 1) * psz] for i in range(pc)]
    exts = [tables[es + j * esz_l: es + (j + 1) * esz_l] for j in range(ec)]
    groups = tables[gs:gs + gc * gsz]
    devices = tables[ds:ds + dc * dsz]

    for j in range(pc):
        nm = parts[j][:36].split(b"\0")[0].decode(errors="replace")
        if nm in PARTITIONS:
            first, num = PARTITIONS[nm]
            attrs = struct.unpack_from("<I", parts[j], 36)[0]
            gidx = struct.unpack_from("<I", parts[j], 52)[0]
            parts[j] = parts[j][:36] + struct.pack("<IIII", attrs, first, num, gidx)
    new_exts = []
    for sect, rel in EXTENTS:
        new_exts.append(struct.pack("<QIQI", sect, 0, rel, 0))
    while len(new_exts) < ec:
        new_exts.append(bytes(esz_l))
    ec_new = max(ec, len(new_exts))
    while len(new_exts) < ec_new:
        new_exts.append(bytes(esz_l))
    pb = b"".join(parts)
    eb = b"".join(new_exts)

    # aggiorna il maximum_size del group default se presente
    new_groups = bytearray(groups)
    for gi in range(gc):
        g = new_groups[gi * gsz:(gi + 1) * gsz]
        if b"default" in g[:36]:
            struct.pack_into("<Q", new_groups, gi * gsz + 40, GROUP_MAX)
    nb = pb + eb + bytes(new_groups) + devices
    assert len(nb) <= hs and False is False, "ok"
    # il blob delle tabelle deve stare tra hs e meta_max
    assert hs + len(nb) <= meta_max, f"tabelle troppo grandi: {len(nb)}"

    block = bytearray(m)          # header esistente (256B) + tabelle
    block[hs:meta_max] = nb + bytes(meta_max - hs - len(nb))
    struct.pack_into("<I", block, 44, len(nb))
    block[48:80] = hashlib.sha256(nb).digest()
    for o, v in ((80, (0, pc, psz)), (92, (len(pb), ec_new, esz_l)),
                 (104, (len(pb) + len(eb), gc, gsz)),
                 (116, (len(pb) + len(eb) + gc * gsz, dc, dsz))):
        struct.pack_into("<III", block, o, *v)
    block[12:44] = hashlib.sha256(bytes(block[:12]) + bytes(32) + bytes(block[44:hs])).digest()
    # CRC32C del blocco metadata (header+tables) senza il campo checksum @0
    block[0:4] = struct.pack("<I", crc32c(bytes(block[4:meta_max])))

    # scrivi primario (slot 0 @12288) e backup (slot 0 in fondo al super)
    backup_abs = super_start + super_size - meta_max * slot_count
    with RAW.open("r+b") as f:
        f.seek(super_start + 12288)
        f.write(block)
        f.seek(backup_abs)
        f.write(block)
    print(f"[OK] metadata scritti: primario @super+12288, backup @super+{backup_abs - super_start} "
          f"(crc32c {struct.unpack_from('<I', block, 0)[0]:#x})")

if __name__ == "__main__":
    main()
