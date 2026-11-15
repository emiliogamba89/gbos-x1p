#!/usr/bin/env python3
"""Neutralizza il descriptor hashtree di "system" nei vbmeta_a/b:
cambia il tag AVB_DESCRIPTOR_TAG_HASHTREE (3) in un tag ignoto; libavb
salta i descriptor sconosciuti -> nessuna verity table per system_a
(stesso stato del vendor, che non ha descriptor e monta pulito).
La firma AVB non e' bloccante nel flusso recovery (libfs_avb: "Failed to
verify vbmeta digest" -> "avb_handle Success").
"""
import re
import struct
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent.parent / "downloads/mica-16471258/disk-writable.raw"
SECT = 512
TAG_HASHTREE = 1  # AVB: 0=property, 1=hashtree, 2=hash, 3=kernel_cmdline
TAG_NEUTRAL = 0x6E657655  # "Uven" — tag sconosciuto, ignorato da libavb

def main():
    with RAW.open("rb") as f:
        f.seek(512)
        h = f.read(92)
        ent_lba, n, esz = struct.unpack_from("<QII", h, 72)
        f.seek(ent_lba * SECT)
        entries = f.read(n * esz)
    targets = []
    for i in range(n):
        e = entries[i * esz:(i + 1) * esz]
        if e[:16] == b"\x00" * 16:
            continue
        name = e[56:128].decode("utf-16-le").rstrip("\x00")
        first, last = struct.unpack_from("<QQ", e, 32)
        if name in ("vbmeta_a", "vbmeta_b"):
            targets.append((name, first * SECT))

    with RAW.open("r+b") as f:
        for name, off in targets:
            f.seek(off)
            assert f.read(4) == b"AVB0"
            f.seek(off + 12)
            # AVB e' BIG-ENDIAN ovunque
            auth_size = struct.unpack(">Q", f.read(8))[0]
            aux_abs = off + 256 + auth_size
            f.seek(off + 96)
            d_off, d_size = struct.unpack(">QQ", f.read(16))
            # i descriptor sono relativi all'inizio del BLOCCO AUSILIARIO
            f.seek(aux_abs + d_off)
            blob = bytearray(f.read(d_size))
            p = 0
            changed = 0
            while p + 16 <= len(blob):
                tag, dlen = struct.unpack_from(">QQ", blob, p)
                if tag == TAG_HASHTREE:
                    # il layout descriptor e' custom (avbtool mica): cerco il
                    # nome partizione come bytes NUL-terminati nel payload
                    payload = bytes(blob[p + 16: p + 16 + dlen])
                    # "system" ma non "system_dlkm"/"system_ext"
                    if re.search(rb"system(?![a-z_0-9])", payload):
                        print(f"{name}: hashtree 'system' @desc+{p} (len {dlen}) -> neutralizzo (tag {TAG_NEUTRAL:#x})")
                        struct.pack_into(">Q", blob, p, TAG_NEUTRAL)
                        changed += 1
                p += 16 + ((dlen + 7) // 8) * 8
            print(f"{name}: descriptor system neutralizzati ora: {changed}")
            f.seek(aux_abs + d_off)
            f.write(blob)
    print("[OK] completato (vbmeta_a: descriptor system senza verity; vbmeta_b non lo contiene)")

if __name__ == "__main__":
    main()
