#!/usr/bin/env python3
"""Ricostruisce l'initrd v4 con SPLICE CHIRURGICO a byte grezzi: trova
l'entry del fstab first-stage nel cpio decompresso e sostituisce SOLO la sua
regione (header filesize + dati, ripadded); tutto il resto — trailer,
archivi concatenati successivi, coda — resta byte-identico.
Uso: rebuild_initrd_v4.py <initrd_v3.img> <initrd_v4.img>
"""
import gzip, sys

src, dst = sys.argv[1], sys.argv[2]
raw = gzip.open(src, "rb").read()
TARGET = b"first_stage_ramdisk/fstab.android-desktop"

pos = 0
found = None
while pos < len(raw) and raw[pos:pos + 6] in (b"070701", b"070702"):
    f = [int(raw[pos + 6 + i * 8: pos + 6 + (i + 1) * 8], 16) for i in range(13)]
    namesize, fsize = f[11], f[6]
    name = raw[pos + 110: pos + 110 + namesize - 1]
    data_start = (pos + 110 + namesize + 3) & ~3
    next_start = (data_start + fsize + 3) & ~3
    if name == TARGET:
        found = (pos, data_start, fsize, next_start)
        break
    pos = next_start
    if name == b"TRAILER!!!":
        # salta il padding di fine archivio e cerca il successivo concatenato
        while pos < len(raw) and raw[pos] == 0:
            pos += 1
assert found, "fstab non trovato nel cpio"
hpos, data_start, fsize, next_start = found

fstab = raw[data_start:data_start + fsize]
new_fstab = (fstab.replace(b",avb=vbmeta", b"")
                  .replace(b"avb=vbmeta,", b"")
                  .replace(b"avb=vbmeta", b""))
assert len(new_fstab) < fsize

hdr = bytearray(raw[hpos:hpos + 110])
hdr[6 + 6 * 8: 6 + 7 * 8] = b"%08X" % len(new_fstab)
name_field = raw[hpos + 110:data_start]
pad = (-(len(new_fstab))) % 4

out = (raw[:hpos] + bytes(hdr) + name_field + new_fstab + b"\0" * pad
       + raw[next_start:])
assert len(out) == len(raw) - (fsize - len(new_fstab))
with open(dst, "wb") as fo:
    fo.write(gzip.compress(out, 6))
print(f"[OK] {dst}: fstab {fsize}->{len(new_fstab)} byte, cpio {len(raw)}->{len(out)}")
