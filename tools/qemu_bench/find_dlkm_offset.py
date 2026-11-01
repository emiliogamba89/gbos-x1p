#!/usr/bin/env python3
"""Trova l'offset (assoluto nel file recovery) di una dynamic partition dentro
il super, leggendo il metadata LP (liblp v10.x) in modo euristico:

 1. cerca le entry LpMetadataPartition per nome (name[36] + attrs + first + num)
 2. cerca la run contigua di LpMetadataExtent (24 byte) nel blocco metadata
 3. calcola gli offset assoluti e verifica il magic EROFS sul disco

Uso: python find_dlkm_offset.py [nome]      (default: system_dlkm_a)
"""
import json
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RECOVERY = os.path.join(BASE, "downloads", "mica", "android-desktop_signed_recovery_image.bin")
V4 = os.path.join(BASE, "downloads", "mica", "v4")

LP_HEADER_MAGIC = 0x414C5030
EROS_MAGIC = b"\xe2\xe1\xf5\xe0"
SUPER_SECTORS_MAX = 40 * 2**30 // 512


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    target = sys.argv[1] if len(sys.argv) > 1 else "system_dlkm_a"
    parts = json.load(open(os.path.join(V4, "gpt-parts.json")))
    super_start, super_end = parts["super"]
    super_sectors = (super_end - super_start) // 512

    with open(RECOVERY, "rb") as f:
        f.seek(super_start)
        super_data = f.read(super_end - super_start)

    # blocco metadata: prova 12288
    base = 12288
    if struct.unpack_from("<I", super_data, base)[0] != LP_HEADER_MAGIC:
        print("[!] header LP non a 12288")
        return 1
    block = super_data[base: base + 65536]

    # 1. partizioni per nome
    parts_info = {}
    for name in (b"system_a", b"vendor_a", b"product_a", b"system_ext_a",
                 b"system_dlkm_a", b"vendor_dlkm_a", b"system_b", b"vendor_b"):
        idx = 0
        while True:
            idx = block.find(bname := name + b"\0", idx)
            if idx < 0:
                break
            # entry: name[36] + attrs u32 + first u32 + num u32 (48 byte)
            first, num = struct.unpack_from("<II", block, idx + 40)
            if num <= 64 and first + num < 4096:
                parts_info[name.decode()] = (idx, first, num)
            idx += 1
    print("[i] partizioni trovate nel metadata:")
    for n, (o, first, num) in parts_info.items():
        print(f"     {n:16s} entry@{o} first_extent={first} num={num}")

    if target not in parts_info:
        print(f"[!] {target} non trovato")
        return 1
    _, first, num = parts_info[target]

    # 2. run di extents: scansione plausibili
    cands = []
    for o in range(0, len(block) - 24, 8):
        sectors, ttype, data, src = struct.unpack_from("<QIqI", block, o)
        if 0 < sectors <= super_sectors and ttype == 0 and \
                0 <= data < super_sectors and src == 0:
            cands.append((o, sectors, data))
    # la run piu' lunga con step 24
    best, run = [], []
    prev = None
    for c in cands:
        if prev is not None and c[0] - prev == 24:
            run.append(c)
        else:
            if len(run) > len(best):
                best = run
            run = [c]
        prev = c[0]
    if len(run) > len(best):
        best = run
    if not best:
        print("[!] nessuna run di extents trovata")
        return 1
    ext_off, ext_count = best[0][0], len(best)
    print(f"[i] tabella extents: @ {ext_off}, {ext_count} entries")

    # 3. extents della partizione target + verifica magic EROFS
    result = []
    f = open(RECOVERY, "rb")
    for k in range(first, first + num):
        if k >= ext_count:
            break
        _, sectors, data = best[k]
        abs_off = super_start + data * 512
        f.seek(abs_off)
        magic = f.read(8)
        ok = magic[:4] == EROS_MAGIC
        print(f"     extent {k}: offset={abs_off} size={sectors*512} "
              f"magic={magic[:4].hex()} {'EROS OK' if ok else '??'}")
        result.append([abs_off, sectors * 512])
    if not any(True for _ in result):
        print("[!] nessun extent")
        return 1
    json.dump({"partition": target, "extents_abs": result},
              open(os.path.join(V4, "dlkm-offsets.json"), "w"), indent=1)
    print("[OK] scritto dlkm-offsets.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
