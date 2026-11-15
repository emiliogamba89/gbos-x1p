#!/usr/bin/env python3
"""Ricannonizza la tabella extents/partizioni LP allo stato noto-buono
(prepatch, verificato in boot) + la seconda extent di system_a (24MiB)
in coda. Nessuna reindicizzazione: gli indici sono hardcoded dallo stato
verificato del boot prepatch.
"""
import hashlib, struct
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent.parent / "downloads/mica-16471258/disk-writable.raw"
SECT = 512

# (sect, rel) nello stato prepatch + la coda per system_a
EXTENTS = [
    (2112200, 2048),       # [0] system_a principale
    (49152, 15815496),     # [1] system_a estensione (append come extend_super)
    (8569832, 2115584),    # [2] system_b
    (753808, 10686464),    # [3] vendor_a principale
    (43992, 15699896),     # [4] vendor_a estensione
    (8, 2114248),          # [5] vendor_a micro
    (8, 2114256),          # [6] vendor_a micro
    (16, 2114264),         # [7] vendor_a micro
    (71608, 15743888),     # [8] vendor_a estensione 2
    (3847672, 11442176),   # [9] product_a
    (357200, 15290368),    # [10] system_ext_a
    (16568, 15648768),     # [11] system_dlkm_a
    (32768, 15667200),     # [12] vendor_dlkm_a
]
PARTITIONS = {  # name -> (first_extent_index, num)
    "system_a": (0, 2),
    "system_b": (2, 1),
    "vendor_a": (3, 6),
    "product_a": (9, 1),
    "system_ext_a": (10, 1),
    "system_dlkm_a": (11, 1),
    "vendor_dlkm_a": (12, 1),
}

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
    tables = bytes(m[hs:hs + struct.unpack_from("<I", m, 44)[0]])
    ps, pc, psz = struct.unpack_from("<III", m, 80)
    es, ec, esz_l = struct.unpack_from("<III", m, 92)
    gs, gc, gsz = struct.unpack_from("<III", m, 104)
    ds, dc, dsz = struct.unpack_from("<III", m, 116)

    parts = [tables[ps + i * psz: ps + (i + 1) * psz] for i in range(pc)]
    exts = [tables[es + j * esz_l: es + (j + 1) * esz_l] for j in range(ec)]
    groups = tables[gs:gs + gc * gsz]
    devices = tables[ds:ds + dc * dsz]

    # riscrivi le partition entries (first/num) e le extents nella nostra
    # disposizione canonica; tutte le entries conservano attributi/attrib flags
    new_exts = []
    for sect, rel in EXTENTS:
        new_exts.append(struct.pack("<QIQI", sect, 0, rel, 0))
    while len(new_exts) < ec:  # conserva eventuali slot extra a zero
        new_exts.append(bytes(esz_l))
    eb = b"".join(new_exts)
    ec_new = len(new_exts)

    for j in range(pc):
        nm = parts[j][:36].split(b"\0")[0].decode()
        if nm in PARTITIONS:
            first, num = PARTITIONS[nm]
            parts[j] = parts[j][:36] + struct.pack("<IIII",
                                                   struct.unpack_from("<I", parts[j], 36)[0],
                                                   first, num,
                                                   struct.unpack_from("<I", parts[j], 48)[0])
    pb = b"".join(parts)

    # groups: aggiorna maximum_size del default
    new_groups = bytearray()
    for gi in range(gc):
        g = bytearray(groups[gi * gsz:(gi + 1) * gsz])
        gname = g[:36].split(b"\0")[0].decode(errors="replace")
        if "default" in gname:
            struct.pack_into("<Q", g, 40, GROUP_MAX)
            print(f"group {gname}: max -> {GROUP_MAX}")
        new_groups += g

    nb = pb + eb + bytes(new_groups) + devices
    struct.pack_into("<I", m, 44, len(nb))
    m[48:80] = hashlib.sha256(nb).digest()
    m[hs:hs + len(nb)] = nb
    for o, v in ((80, (0, pc, psz)), (92, (len(pb), ec_new, esz_l)),
                 (104, (len(pb) + len(eb), gc, gsz)),
                 (116, (len(pb) + len(eb) + len(groups), dc, dsz))):
        struct.pack_into("<III", m, o, *v)
    m[12:44] = hashlib.sha256(bytes(m[:12]) + bytes(32) + bytes(m[44:hs])).digest()
    with RAW.open("r+b") as f:
        f.seek(super_start + 12288)
        f.write(m)
    total = sum(e[0] for e in EXTENTS)
    print(f"[OK] LP riscritti: {ec_new} extents, {total*SECT>>20} MiB totali; "
          f"partitions: {PARTITIONS}")

if __name__ == "__main__":
    main()
