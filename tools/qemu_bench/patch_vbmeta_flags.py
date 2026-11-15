#!/usr/bin/env python3
"""Setta i flag disable-verity + disable-verification nei header vbmeta_a/b.
Solo per il disco legacy su drvfs; per disk-run.raw usare invece
restore_vbmeta_test.py, che ripristina AVB0 e salva backup prima della patch.
Il guest unlocked accetta l'errore firma e restituisce VerificationDisabled.
La patch header invalida la firma: non usarla su dispositivi locked.
"""
import struct
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent.parent / "downloads/mica-16471258/disk-writable.raw"
SECT = 512
FLAGS = 3  # bit0 HASHTREE_DISABLED, bit1 VERIFICATION_DISABLED

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
            magic = f.read(4)
            assert magic == b"AVB0", f"{name}: magic {magic!r} non e' AVB0"
            f.seek(off + 120)
            old = struct.unpack(">I", f.read(4))[0]
            f.seek(off + 120)
            f.write(struct.pack(">I", FLAGS))  # avbtool usa BIG-ENDIAN
            print(f"{name} @ {off}: flags {old} -> {FLAGS}")
    print("[OK] flag scritti; verificare nel guest: VerificationDisabled / AVB HASHTREE disabled")

if __name__ == "__main__":
    main()
