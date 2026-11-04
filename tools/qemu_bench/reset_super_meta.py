#!/usr/bin/env python3
"""Ripristina nel disco scrivibile le aree metadati del super dall'immagine
recovery ORIGINALE (geometry + slot LP), annullando eventuali esperimenti
falliti sui metadati LP. Il GPT NON viene toccato (le estensioni gia' fatte
a super.last restano). Le aree dati delle dynamic partitions restano intatte:
vendor_a verra' riscritto da vendor_port.py al passo successivo.

Uso: python3 reset_super_meta.py
"""
import shutil
import struct
import zlib
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
WRITABLE = BASE / "downloads" / "mica-16471258" / "disk-writable.raw"
ORIG = BASE / "downloads" / "mica-16471258" / "android-desktop_signed_recovery_image.bin"
SUPER_START = 344064 * 512
# geometry @super+4096 + slot metadata: copiamo una finestra comoda di 24 KiB
# (geometry 4 KiB + slot 0/1 con metadata_max_size fino a 8 KiB)
REGION_OFF = 4096
REGION_LEN = 24576


def restore_gpt():
    """Ripristina nel GPT del disco scrivibile l'entry del super originale
    (annulla eventuali estensioni: super.last torna al valore pristine)."""
    def gpt(f, base=512):
        f.seek(base)
        h = bytearray(f.read(92))
        ent_lba, n, esz = struct.unpack_from("<QII", h, 72)
        f.seek(ent_lba * 512)
        e = bytearray(f.read(n * esz))
        return h, e

    with ORIG.open("rb") as fo, WRITABLE.open("r+b") as fd:
        ho, eo = gpt(fo)
        hw, ew = gpt(fd)
        esz = struct.unpack_from("<I", ho, 84)[0]
        si = so = None
        for i in range(len(eo) // esz):
            if eo[i * esz:(i + 1) * esz][56:128].decode("utf-16-le").split("\0")[0] == "super":
                si = i
        # copia SOLO la entry super (first/last) nel disco scrivibile, con CRC
        fd.seek(512)
        hw2 = bytearray(fd.read(92))
        ent_lba = struct.unpack_from("<Q", hw2, 72)[0]
        off = si * esz
        ew[off + 32:off + 48] = eo[off + 32:off + 48]
        crc_e = zlib.crc32(bytes(ew)) & 0xFFFFFFFF
        struct.pack_into("<I", hw2, 88, crc_e)
        hw2[16:20] = bytes(4)
        hs = struct.unpack_from("<I", hw2, 12)[0]
        struct.pack_into("<I", hw2, 16, zlib.crc32(bytes(hw2[:hs])) & 0xFFFFFFFF)
        fd.seek(512)
        fd.write(hw2)
        fd.seek(ent_lba * 512)
        fd.write(ew)
        # backup GPT: header all'ultimo settore, entry prima
        disk_lba = WRITABLE.stat().st_size // 512 - 1
        fd.seek(disk_lba * 512)
        hb2 = bytearray(fd.read(92))
        bent_lba = struct.unpack_from("<Q", hb2, 72)[0]
        fd.seek(bent_lba * 512)
        fd.write(ew)
        fd.seek(disk_lba * 512)
        hb2[16:20] = bytes(4)
        struct.pack_into("<I", hb2, 88, crc_e)
        hs = struct.unpack_from("<I", hb2, 12)[0]
        struct.pack_into("<I", hb2, 16, zlib.crc32(bytes(hb2[:hs])) & 0xFFFFFFFF)
        fd.seek(disk_lba * 512)
        fd.write(hb2)
    first, last = struct.unpack_from("<QQ", eo[si * esz:(si + 1) * esz], 32)
    print(f"[GPT] super ripristinato all'originale: [{first}..{last}]")


def main():
    restore_gpt()
    with ORIG.open("rb") as src, WRITABLE.open("r+b") as dst:
        src.seek(SUPER_START + REGION_OFF)
        data = src.read(REGION_LEN)
        dst.seek(SUPER_START + REGION_OFF)
        dst.write(data)
    print(f"[OK] ripristinati {REGION_LEN} byte di metadati super dall'originale "
          f"(@super+{REGION_OFF}..+{REGION_OFF + REGION_LEN})")


if __name__ == "__main__":
    main()
