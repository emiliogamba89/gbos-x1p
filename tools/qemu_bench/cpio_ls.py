#!/usr/bin/env python3
"""Elenca/estrae initrd (cpio newc gzippato) senza cpio(1)."""
import gzip, sys

img = sys.argv[1]
want = sys.argv[2] if len(sys.argv) > 2 else None  # None = lista nomi
data = gzip.open(img, "rb").read()
pos = 0
while pos < len(data):
    if data[pos:pos + 6] != b"070701":
        break
    def hdr(off):
        return [int(data[off + 6 + i * 8: off + 6 + (i + 1) * 8], 16) for i in range(13)]
    (ino, mode, uid, gid, nlink, mtime, fsize, dmaj, dmin,
     rmaj, rmin, namesize, chk) = hdr(pos)
    name = data[pos + 110: pos + 110 + namesize - 1].decode()
    fstart = (pos + 110 + namesize + 3) & ~3
    fdata = data[fstart:fstart + fsize]
    nxt = (fstart + fsize + 3) & ~3
    if name == "TRAILER!!!":
        break
    pos = nxt
    if want is None:
        print(name)
    elif want == name.lstrip("./"):
        sys.stdout.buffer.write(fdata)
        break
