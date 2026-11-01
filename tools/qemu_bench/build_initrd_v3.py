#!/usr/bin/env python3
"""Costruisce l'initrd v3 stile gbos-vm:

  blob gzip unico = [vendor_0_platform.cpio][init_ramdisk.cpio][override]

Il frammento 'recovery' del vendor_boot viene SCARTATO (era lui a imporre
modules.load.recovery con i moduli Qualcomm). L'override sovrascrive
lib/modules/modules.load(.recovery) con una lista minimale per QEMU virt.

Output: downloads/mica/payload/initrd_v3.img, cmdline_v3.txt
"""
import gzip
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V4 = os.path.join(BASE, "downloads", "mica", "v4")
OUT = os.path.join(BASE, "downloads", "mica", "payload")

# lista moduli per QEMU virt: solo senza catene problematiche
MODULES_LOAD = b"icc-clk.ko\n"

CMDLINE_V3 = ("console=ttyAMA0,115200 earlycon=pl011,0x9000000 panic=0 root=/dev/ram0 "
              "androidboot.hardware=android-desktop androidboot.hardware.platform=android-desktop "
              "androidboot.slot_suffix=_a androidboot.boot_devices=3f000000.pcie "
              "androidboot.baseband=apq androidboot.load_modules_parallel=true "
              "androidboot.vbmeta.device_state=unlocked androidboot.verifiedbootstate=orange "
              "androidboot.veritymode=enforcing printk.devkmsg=on loglevel=7 ignore_loglevel")


def cpio_entry(name, data):
    out = bytearray()
    names = name.encode() + b"\x00"
    hdr = "070701"
    for v in [0, 0o100644, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(names), 0]:
        hdr += f"{v:08X}"
    out += hdr.encode() + names
    while len(out) % 4:
        out += b"\x00"
    out += data
    while len(out) % 4:
        out += b"\x00"
    return bytes(out)


def cpio_trailer():
    return cpio_entry("TRAILER!!!", b"")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    platform = open(os.path.join(V4, "vendor_0_platform.cpio"), "rb").read()
    init_rd = open(os.path.join(V4, "init_ramdisk.cpio"), "rb").read()

    # override: lista moduli per qemu (sia normale che recovery)
    # + i metadata dei moduli del platform cpio restano validi (icc-clk non ha dipendenze)
    override = b""
    for path in ("lib/modules/modules.load", "lib/modules/modules.load.recovery"):
        override += cpio_entry(path, MODULES_LOAD)
    override += cpio_trailer()

    blob = platform + init_rd + override
    img = gzip.compress(blob, compresslevel=6, mtime=0)
    open(os.path.join(OUT, "initrd_v3.img"), "wb").write(img)
    open(os.path.join(OUT, "cmdline_v3.txt"), "w").write(CMDLINE_V3)

    print(f"[OK] initrd_v3.img: {len(img)} byte "
          f"(platform {len(platform)} + init {len(init_rd)} + override {len(override)})")
    print(f"[OK] cmdline_v3.txt: {CMDLINE_V3[:80]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
