#!/usr/bin/env python3
"""Estrae i moduli virtio GPU/input dal vendor_boot Cuttlefish (RAMDISK_MODULES
del gbos-vm): virtio-gpu.ko, virtio_input.ko, virtio_dma_buf.ko + modules.dep.

Riusa il parser VNDRBOOT v4 di mica_v4.py. Gira su Windows (python con lz4).
"""
import io
import json
import os
import struct
import sys
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CF = os.path.join(BASE, "downloads", "cuttlefish")
OUT = os.path.join(CF, "extract", "cf-modules")

WANT = ["virtio-gpu.ko", "virtio_input.ko", "virtio_dma_buf.ko",
        "modules.dep", "modules.alias", "modules.softdep", "modules.options"]


def u(b, o):
    return struct.unpack_from("<I", b, o)[0]


def lz4_stream(data, pos, end):
    import lz4.block
    out = b""
    while pos < end:
        magic = struct.unpack_from("<I", data, pos)[0]
        if magic != 0x184d2104:
            break
        bsize = u(data, pos + 4)
        pos += 8
        bstart = pos
        while pos < min(bstart + bsize, end):
            token = data[pos]
            lit_len = token >> 4
            p = pos + 1
            if lit_len == 15:
                while True:
                    ext = data[p]
                    p += 1
                    lit_len += ext
                    if ext != 255:
                        break
            pos = p + lit_len
            if pos >= bstart + bsize:
                out += lz4.block.decompress(data[bstart:pos],
                                            uncompressed_size=bsize * 4 + 4096)
                pos = bstart + bsize
                break
            pos += 2
            while pos < bstart + bsize and data[pos - 1] == 255:
                pos += 1
        pos = bstart + bsize
    return out


def decompress_blob(blob):
    if blob[:2] == b"\x1f\x8b":
        import gzip
        return gzip.decompress(blob)
    if blob[:4] == bytes.fromhex("04224d18"):
        return lz4_stream(blob, 0, len(blob))
    if blob[:4] == bytes.fromhex("02214c18"):
        # LZ4 legacy: [magic][compressed u32][data] * N, max 8 MiB per blocco
        import lz4.block
        out, pos = b"", 4
        while pos < len(blob):
            csz = u(blob, pos)
            out += lz4.block.decompress(blob[pos + 4:pos + 4 + csz],
                                        uncompressed_size=8 * 1024 * 1024)
            pos += 4 + csz
        return out
    return blob


def cpio_find(cpio, path):
    pos = 0
    while pos + 110 <= len(cpio):
        if cpio[pos:pos + 6] != b"070701":
            break

        def fld(i, p=pos):
            return int(cpio[p + 6 + i * 8:p + 6 + (i + 1) * 8], 16)
        filesize, namesize = fld(6), fld(11)
        name = cpio[pos + 110:pos + 110 + namesize - 1].decode(errors="replace")
        dstart = (pos + 110 + namesize + 3) & ~3
        if name == path:
            return cpio[dstart:dstart + filesize]
        pos = (dstart + filesize + 3) & ~3
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(OUT, exist_ok=True)
    z = zipfile.ZipFile(os.path.join(CF, "cf-img.zip"))
    vb = z.read("vendor_boot.img")
    assert vb[:8] == b"VNDRBOOT" and u(vb, 8) == 4, "VNDRBOOT v4 atteso"
    page, vs = u(vb, 12), u(vb, 24)
    hs, dtb = u(vb, 2096), u(vb, 2100)
    ts, count, es, bs = struct.unpack_from("<IIII", vb, 2112)
    start = (hs + page - 1) // page * page
    table = start + (vs + page - 1) // page * page + (dtb + page - 1) // page * page

    found = {}
    for j in range(count):
        e = vb[table + j * es: table + (j + 1) * es]
        size, off, kind = struct.unpack_from("<III", e)
        name = e[12:44].split(b"\0")[0].decode() or "platform"
        frag = decompress_blob(vb[start + off:start + off + size])
        for w in WANT:
            if w in found:
                continue
            data = cpio_find(frag, "lib/modules/" + w)
            if data is not None:
                found[w] = data
                open(os.path.join(OUT, w), "wb").write(data)
    for w in WANT[:3]:
        assert w in found, f"{w} non trovato nel vendor_boot CF"
    print("[OK] moduli CF estratti in", OUT)
    for w, d in sorted(found.items()):
        print(f"  {w}: {len(d)} byte")
    dep = found.get("modules.dep", b"")
    for w in WANT[:3]:
        lines = [l for l in dep.splitlines() if w.replace("-", "_") in
                 l.decode(errors="replace")]
        for l in lines:
            print("  dep:", l.decode(errors="replace")[:160])


if __name__ == "__main__":
    main()
