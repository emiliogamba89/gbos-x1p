#!/usr/bin/env python3
"""Fase 2 / banco QEMU - costruisce il payload di boot dal recovery mica estratto.

Composizione (fedele al boot Android di mica):
  kernel  = boot_a[4096 : 4096+kernel_size]                    (GKI 19.5 MiB)
  initrd  = init_boot ramdisk + vendor_boot ramdisk blob       (membri cpio
            concatenati, ciascuno compresso lz4: il kernel GKI li gestisce)
  cmdline = variante Q1 minimale (console=ttyAMA0 per QEMU virt PL011)

Output: downloads/mica/payload/{kernel.bin, initrd.img, cmdline_q1.txt, cmdline_mica.txt}
"""
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXT = os.path.join(BASE, "downloads", "mica", "extract")
OUT = os.path.join(BASE, "downloads", "mica", "payload")

CMDLINE_Q1 = ("clk_ignore_unused pd_ignore_unused root=/dev/ram0 init=/init "
              "console=ttyAMA0 firmware_class.path=/vendor/firmware")
CMDLINE_MICA = ("clk_ignore_unused pd_ignore_unused efi=noruntime efi=novamap "
                "android_arch_task_struct_size=512 id_aa64mmfr1.vh=0 arm64_sw.hvhe=0 "
                "irqaffinity=0-3 pcie_ports=compat root=/dev/ram0 console=null "
                "firmware_class.path=/vendor/firmware,/vendor/firmware_mnt/image bootconfig")


def lz4_stream(data, pos, end):
    """Decomprime un flusso LZ4 legacy (blocchi, flag raw, endmark, frammenti)."""
    out = bytearray()
    while pos + 4 <= end:
        csz = struct.unpack_from("<I", data, pos)[0]
        if csz == 0:
            return out, pos + 4
        if csz == 0x184C2102:          # nuovo frammento: esce senza consumare
            return out, pos
        raw = bool(csz & 0x80000000)
        csz &= 0x7FFFFFFF
        pos += 4
        if raw:
            out += data[pos:pos + csz]
        else:
            import lz4.block
            out += lz4.block.decompress(data[pos:pos + csz],
                                        uncompressed_size=32 * 1024 * 1024)
        pos += csz
    return out, pos


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    boot = open(os.path.join(EXT, "boot_a.img"), "rb").read()
    ksize = int.from_bytes(boot[8:12], "little")
    blob = boot[4096:4096 + ksize]

    # il kernel mica è Image compressa LZ4 legacy (eventuali frammenti concatenati)
    parts, pos = [], 0
    while pos + 4 <= len(blob):
        if struct.unpack_from("<I", blob, pos)[0] != 0x184C2102:
            break
        part, pos = lz4_stream(blob, pos + 4, len(blob))
        parts.append(part)
    kernel = b"".join(parts)
    if parts:
        print(f"[i] kernel Image.lz4: {len(blob)} byte -> decompressi {len(kernel)} byte "
              f"({len(parts)} frammenti, consumati {pos})")
    else:
        kernel = blob
        print("[i] kernel non compresso lz4")

    if kernel[0x38:0x3C] != b"ARM\x64":
        print(f"[!] ATTENZIONE: magic ARM64 Image mancante @0x38: {kernel[0x38:0x3C]!r}")
        sys.exit(1)
    print(f"[OK] kernel: magic ARM64 Image valido, {len(kernel)} byte")

    ib = open(os.path.join(EXT, "init_boot_a.img"), "rb").read()
    rsize = int.from_bytes(ib[12:16], "little")
    init_rd = ib[4096:4096 + rsize]

    vb = open(os.path.join(EXT, "vendor_boot_a.img"), "rb").read()
    vsize = int.from_bytes(vb[24:28], "little")
    vendor_rd = vb[4096:4096 + vsize]

    initrd = init_rd + vendor_rd

    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "kernel.bin"), "wb").write(kernel)
    open(os.path.join(OUT, "initrd.img"), "wb").write(initrd)
    open(os.path.join(OUT, "cmdline_q1.txt"), "w").write(CMDLINE_Q1)
    open(os.path.join(OUT, "cmdline_mica.txt"), "w").write(CMDLINE_MICA)

    print(f"[OK] payload in {OUT}:")
    print(f"     kernel.bin  {len(kernel)} byte")
    print(f"     initrd.img  {len(initrd)} byte (init_boot {len(init_rd)} + vendor {len(vendor_rd)})")
    print(f"     cmdline_q1.txt / cmdline_mica.txt")
    print("\nProssimo passo: run_qemu (vedi docs/QEMU-BENCH.md)")


if __name__ == "__main__":
    sys.exit(main())
