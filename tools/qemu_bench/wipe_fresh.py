#!/usr/bin/env python3
"""Azzera metadata e userdata nel disco QEMU scrivibile (mai nell'originale):
il vold le formatta al primo boot e crea chiavi FBE nuove col KeyMint
software — il trucco "fresh userdata" della ricetta gbos-vm, senza riscrivere
la GPT. Le partizioni nel fstab hanno il flag formattable.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
WRITABLE = BASE / "downloads" / "mica-16471258" / "disk-writable.raw"
ORIG = BASE / "downloads" / "mica-16471258" / "android-desktop_signed_recovery_image.bin"
OUT = BASE / "downloads" / "mica-16471258" / "wipe-fresh.json"
TARGETS = {"metadata", "userdata"}
CHUNK = 4 << 20


def parts(raw):
    out = {}
    with raw.open("rb") as f:
        f.seek(512)
        h = f.read(92)
        ent_lba, n, esz = struct.unpack_from("<QII", h, 72)
        for i in range(n):
            f.seek(ent_lba * 512 + i * esz)
            e = f.read(esz)
            if e[:16] == bytes(16):
                continue
            name = e[56:128].decode("utf-16-le").split("\0")[0]
            a, b = struct.unpack_from("<QQ", e, 32)
            out[name] = (a * 512, (b + 1) * 512)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not WRITABLE.exists():
        raise SystemExit("manca disk-writable.raw: esegui prima WRITABLE_DISK=1 run_qemu.sh")
    p = parts(ORIG)
    zero = bytes(CHUNK)
    report = {}
    with WRITABLE.open("r+b") as f:
        size = f.seek(0, 2)
        for name in sorted(TARGETS):
            start, end = p[name]
            assert end <= size, f"{name} fuori dal disco"
            f.seek(start)
            left = end - start
            while left:
                f.write(zero[: min(left, CHUNK)])
                left -= min(left, CHUNK)
            report[name] = {"start": start, "end": end, "bytes": end - start}
            print(f"[OK] {name}: azzerati {end - start} byte")
    report["sha256_gpt_entries"] = hashlib.sha256(
        ORIG.read_bytes()[1024:1024 + 128 * 128]).hexdigest()
    report["note"] = "solo disk-writable.raw; l'immagine originale non e' toccata"
    OUT.write_text(json.dumps(report, indent=1) + "\n")
    print("[OK]", OUT)


if __name__ == "__main__":
    main()
