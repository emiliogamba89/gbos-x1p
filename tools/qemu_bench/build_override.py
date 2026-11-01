#!/usr/bin/env python3
"""Fase 2 / banco QEMU - override cpio per la Milestone Q2.

Genera:
  downloads/mica/payload/override_q2.cpio   (cpio newc PLAIN)
  downloads/mica/payload/initrd_q2.img      (initrd.img + override concatenati)
  downloads/mica/payload/cmdline_q2.txt

Trucco: i membri cpio dell'initrd si concatenano e per path identici vince
l'ULTIMO membro -> sovrascriviamo lib/modules/modules.load con una lista
ridotta di soli moduli generici (i moduli Qualcomm falliscono su -M virt),
cosi init arriva in fondo alla lista e stampiamo il suo errore finale
(il motivo del reboot 'bootloader').

Il file originale modules.load viene salvato in
downloads/mica/extract/vendor_ramdisk_files/modules.load.orig
"""
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CP = os.path.join(BASE, "downloads", "mica", "extract", "vendor_ramdisk_full.cpio")
OUT = os.path.join(BASE, "downloads", "mica", "payload")

# moduli che hanno senso su -machine virt (ordine preservato dal modules.load;
# SOLO moduli senza catene di dipendenze problematiche: pinctrl-msm tira
# qcom-scm/arm_ffa, debug_symbol porta a camcc via LMP -> reboot)
Q2_KEEP = (
    "qti-regmap-debugfs.ko", "icc-clk.ko", "clk-qcom.ko",
)

CMDLINE_Q2 = ("clk_ignore_unused pd_ignore_unused root=/dev/ram0 init=/init "
              "console=ttyAMA0 loglevel=7 ignore_loglevel "
              "firmware_class.path=/vendor/firmware")


def cpio_entry(name, data):
    out = bytearray()
    names = name.encode() + b"\x00"
    hdr = "070701"
    vals = [0, 0o100644, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(names), 0]
    for v in vals:
        hdr += f"{v:08X}"
    out += hdr.encode()
    out += names
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

    # 1. estrae modules.load dal cpio del vendor ramdisk
    data = open(CP, "rb").read()
    pos = 0
    mods_load = None
    while pos + 110 <= len(data):
        if data[pos:pos+6] != b"070701":
            break
        def fld(i, p=pos):
            return int(data[p+6+i*8:p+6+(i+1)*8], 16)
        filesize, namesize = fld(6), fld(11)
        name = data[pos+110:pos+110+namesize-1].decode(errors="replace")
        dstart = (pos + 110 + namesize + 3) & ~3
        if name == "lib/modules/modules.load":
            mods_load = data[dstart:dstart+filesize]
            break
        pos = (dstart + filesize + 3) & ~3
    if mods_load is None:
        print("[!] modules.load non trovato nel cpio")
        return 1
    fdir = os.path.join(BASE, "downloads", "mica", "extract", "vendor_ramdisk_files")
    os.makedirs(fdir, exist_ok=True)
    open(os.path.join(fdir, "modules.load.orig"), "wb").write(mods_load)
    orig = mods_load.decode(errors="replace").splitlines()
    kept = [l.strip() for l in orig if l.strip() and l.strip() in Q2_KEEP]
    dropped = [l.strip() for l in orig if l.strip() and l.strip() not in Q2_KEEP]
    print(f"[i] modules.load originale: {len(orig)} moduli -> Q2: {len(kept)} "
          f"({len(dropped)} esclusi)")

    # 2. override cpio
    override = cpio_entry("lib/modules/modules.load",
                          ("\n".join(kept) + "\n").encode())
    override += cpio_trailer()
    # padding cpio a 512 per pulizia
    while len(override) % 512:
        override += b"\x00"
    open(os.path.join(OUT, "override_q2.cpio"), "wb").write(override)

    # 3. initrd_q2 = initrd.img + override
    initrd = open(os.path.join(OUT, "initrd.img"), "rb").read()
    open(os.path.join(OUT, "initrd_q2.img"), "wb").write(initrd + override)

    # 4. cmdline q2
    open(os.path.join(OUT, "cmdline_q2.txt"), "w").write(CMDLINE_Q2)

    print(f"[OK] payload: override_q2.cpio ({len(override)} byte), "
          f"initrd_q2.img ({len(initrd) + len(override)} byte), cmdline_q2.txt")
    print(f"[OK] moduli Q2: {', '.join(kept)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
