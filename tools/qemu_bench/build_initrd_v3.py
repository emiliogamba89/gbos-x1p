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
V4 = os.path.join(BASE, "downloads", "mica-16471258", "v4")
OUT = os.path.join(BASE, "downloads", "mica", "payload")

# lista moduli per QEMU virt: solo senza catene problematiche
MODULES_LOAD = b"icc-clk.ko\n"

CMDLINE_V3 = ("console=ttyAMA0,115200 earlycon=pl011,0x9000000 panic=0 root=/dev/ram0 "
              "androidboot.hardware=android-desktop androidboot.hardware.platform=android-desktop "
              "androidboot.slot_suffix=_a androidboot.boot_devices=3f000000.pcie "
              "androidboot.baseband=apq androidboot.load_modules_parallel=true "
              "androidboot.vbmeta.device_state=unlocked androidboot.verifiedbootstate=orange "
              "androidboot.veritymode=enforcing printk.devkmsg=on loglevel=7 ignore_loglevel "
              "androidboot.vendor.apex.com.android.hardware.keymint.strongbox.desktop=none "
              "androidboot.vendor.apex.com.android.hardware.audio.desktop=none")


def cpio_entry(name, data, mode=0o100644):
    out = bytearray()
    names = name.encode() + b"\x00"
    hdr = "070701"
    for v in [0, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(names), 0]:
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

    # override: lista moduli per qemu (normale e recovery) + moduli virtio
    # estratti da system_dlkm (se extract_virtio.sh e' stato lanciato in WSL)
    virtio_dir = os.path.join(V4, "virtio")
    virtio = sorted(os.listdir(virtio_dir)) if os.path.isdir(virtio_dir) else []
    # virtio_pci dipende da legacy_dev/modern_dev: prima i dev, poi il bus
    order = ["virtio_blk.ko", "virtio_console.ko", "virtio_pci_legacy_dev.ko",
             "virtio_pci_modern_dev.ko", "virtio_pci.ko"]
    virtio = [m for m in order if m in virtio] + \
             [m for m in virtio if m not in order]
    load = b"icc-clk.ko\n" + b"".join((m + "\n").encode() for m in virtio)

    # modules.dep ORIGINALE del platform cpio (l'init lo usa per risolvere i
    # nomi) + righe per i moduli virtio aggiunti (senza dipendenze)
    def cpio_find(cpio, path):
        pos = 0
        while pos + 110 <= len(cpio):
            if cpio[pos:pos+6] != b"070701":
                break
            def fld(i, p=pos):
                return int(cpio[p+6+i*8:p+6+(i+1)*8], 16)
            mode, filesize, namesize = fld(1), fld(6), fld(11)
            name = cpio[pos+110:pos+110+namesize-1].decode(errors="replace")
            dstart = (pos + 110 + namesize + 3) & ~3
            if name == path:
                return mode, cpio[dstart:dstart+filesize]
            pos = (dstart + filesize + 3) & ~3
        return None

    dep_mode, dep_orig = cpio_find(platform, "lib/modules/modules.dep") or (0o100644, b"")
    dep_extra = b"/lib/modules/virtio_pci.ko: /lib/modules/virtio_pci_legacy_dev.ko /lib/modules/virtio_pci_modern_dev.ko\n"
    dep_extra += b"".join(("/lib/modules/" + m + ":\n").encode()
                          for m in virtio if m != "virtio_pci.ko")

    # fstab del first stage: il mount vendor modificato (vendor_port.py) omette
    # l'AVB hash obsoleto (come gbos-vm make_mica_gpu_initrd.py)
    fstab_name = "first_stage_ramdisk/fstab.android-desktop"
    fstab_mode, fstab = cpio_find(platform, fstab_name) or (0o100644, b"")
    fstab = b"\n".join(
        l.replace(b",avb=vbmeta", b"") if l.startswith(b"vendor ") else l
        for l in fstab.splitlines()) + b"\n"

    override = b""
    for path in ("lib/modules/modules.load", "lib/modules/modules.load.recovery"):
        override += cpio_entry(path, load)
    for m in virtio:
        override += cpio_entry("lib/modules/" + m,
                               open(os.path.join(virtio_dir, m), "rb").read())
    override += cpio_entry("lib/modules/modules.dep", dep_orig + dep_extra, dep_mode)
    override += cpio_entry(fstab_name, fstab, fstab_mode)
    override += cpio_trailer()

    blob = platform + init_rd + override
    img = gzip.compress(blob, compresslevel=6, mtime=0)
    open(os.path.join(OUT, "initrd_v3.img"), "wb").write(img)
    open(os.path.join(OUT, "cmdline_v3.txt"), "w").write(CMDLINE_V3)

    print(f"[OK] initrd_v3.img: {len(img)} byte "
          f"(platform {len(platform)} + init {len(init_rd)} + override {len(override)})")
    print(f"[OK] moduli in lista: icc-clk.ko{'' if not virtio else ', ' + ', '.join(virtio)}")
    print(f"[OK] fstab: riga vendor senza avb\n    {fstab.decode(errors='replace').strip()[:180]}")
    print(f"[OK] cmdline_v3.txt: {CMDLINE_V3[:80]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
