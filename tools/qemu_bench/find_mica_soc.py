#!/usr/bin/env python3
"""Trova dtbo/boot/vendor_boot nel recovery mica e cerca identificativi SoC/board."""
import re
import struct
import sys

RAW = sys.argv[1] if len(sys.argv) > 1 else \
    "/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/android-desktop_signed_recovery_image.bin"
print("start:", RAW, flush=True)

with open(RAW, "rb") as f:
    f.seek(512)
    hdr = f.read(512)
assert hdr[:8] == b"EFI PART", hdr[:8]
print("sig:", hdr[:8].decode(), flush=True)
num = struct.unpack_from("<I", hdr, 80)[0]
size = struct.unpack_from("<I", hdr, 84)[0]
entries_lba = struct.unpack_from("<Q", hdr, 72)[0]
print("entries_lba:", entries_lba, "num:", num, "size:", size, flush=True)

with open(RAW, "rb") as f:
    f.seek(entries_lba * 512)
    raw_entries = f.read(num * size)

parts = {}
for i in range(num):
    e = raw_entries[i * size:(i + 1) * size]
    if e[:16] == b"\x00" * 16:
        continue
    first, last = struct.unpack_from("<QQ", e, 32)
    name = e[56:128].decode("utf-16-le").rstrip("\x00")
    parts[name] = (first * 512, (last - first + 1) * 512)
    print(f"{name:16s} offset={first * 512:>13,} size={(last - first + 1) * 512:>12,}", flush=True)

targets = ["dtb_a", "dtbo_a", "boot_a", "vendor_boot_a", "init_boot_a"]
patterns = [b"x1e80100", b"x1p42100", b"8380", b"pineapple", b"dell",
            b"xps", b"lenovo", b"qoy"]
for name in targets:
    if name not in parts:
        continue
    off, size = parts[name]
    with open(RAW, "rb") as f:
        f.seek(off)
        data = f.read(min(size, 2 * 1024 * 1024))
    print(f"== {name} ({size:,} byte) ==", flush=True)
    for pat in patterns:
        idx = data.find(pat)
        if idx >= 0:
            ctx = data[max(0, idx - 40):idx + 60]
            ctx = re.sub(rb"[^\x20-\x7e]", b".", ctx).decode()
            print(f"  {pat.decode():10s} @{idx}: ...{ctx}...", flush=True)
print("done", flush=True)
