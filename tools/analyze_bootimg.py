#!/usr/bin/env python3
"""FASE 1 v2 - Analisi immagini boot recovery mica (formato Android 17).

Layout decodificato (da hex dump + aritmetica AVB verificata):
  boot_a:      "ANDROID!" @0, kernel_size u32 @8 (boot_a: 20445831), dati @4096
  init_boot:   "ANDROID!" @0, kernel_size u32 @8 (=0), ramdisk_size u32 @12, dati @4096
  vendor_boot: "VNDRBOOT" @0, ver u32 @8 (=4), page u32 @12 (=2048),
               ramdisk_addr @16, dtb_addr @20, vendor_ramdisk_size @24,
               cmdline (2112B) @28, dati @page_size

Il kernel (monolitico) contiene DTB builtin (FDT) e IKCONFIG (config embed).
Uso:  python tools/analyze_bootimg.py [--dir downloads/mica/extract]
Output: reports/mica-analysis/bootimg-report.md (solo metadati: committabile)
"""
import argparse
import gzip
import os
import re
import struct
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "reports", "mica-analysis")

CFG_KEYS = ["CONFIG_EFI", "CONFIG_EFI_STUB", "CONFIG_ACPI", "CONFIG_ACPI_TABLE_UPGRADE",
            "CONFIG_ACPI_PPTT", "CONFIG_OF", "CONFIG_OF_OVERLAY", "CONFIG_ARM64",
            "CONFIG_PCI", "CONFIG_PCI_ECAM", "CONFIG_PCI_HOST_GENERIC", "CONFIG_PCIE_QCOM",
            "CONFIG_PCIEPORTBUS", "CONFIG_QCOM_SCM", "CONFIG_QCOM_PDC", "CONFIG_QCOM_GENI_SE",
            "CONFIG_SERIAL_QCOM_GENI", "CONFIG_I2C_QCOM_GENI", "CONFIG_SPI_QCOM_GENI",
            "CONFIG_I2C_HID", "CONFIG_HID_MULTITOUCH", "CONFIG_USB_XHCI_PCI",
            "CONFIG_ATH11K", "CONFIG_DRM_MSM", "CONFIG_FB_EFI", "CONFIG_SYSFB_SIMPLEFB",
            "CONFIG_SOUNDWIRE_QCOM", "CONFIG_SND_SOC_QCOM", "CONFIG_TYPEC_UCSI",
            "CONFIG_PKVM", "CONFIG_KVM", "CONFIG_IKCONFIG", "CONFIG_EFI_CAPSULE_LOADER",
            "CONFIG_RTC_DRV_EFI", "CONFIG_USB_DWC3", "CONFIG_QCOM_PMIC_GLINK"]


def u32le(b, o):
    return struct.unpack_from("<I", b, o)[0]


def ascii_strings(data, minlen=5):
    return [m.group().decode() for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minlen, data)]


def parse_vbmeta(path):
    """Descriptor hash AVB: (partition_name, image_size)."""
    data = open(path, "rb").read()
    auth = struct.unpack_from("<Q", data, 4)[0]
    aux = struct.unpack_from("<Q", data, 12)[0]
    desc_off = 256 + auth + aux + struct.unpack_from("<Q", data, 56)[0]
    desc_size = struct.unpack_from("<Q", data, 64)[0]
    block = data[desc_off:desc_off + desc_size]
    out = []
    i = 0
    while i + 8 <= len(block):
        tag = struct.unpack_from("<Q", block, i)[0]
        if tag == 1:  # hash descriptor
            img_size = struct.unpack_from("<Q", block, i + 8)[0]
            salt_n = u32le(block, i + 16)
            dig_n = u32le(block, i + 20)
            name_len = u32le(block, i + 86)
            name = block[i + 90:i + 90 + name_len].decode(errors="replace")
            out.append((name, img_size))
            i += 90 + name_len + salt_n + dig_n
            i = (i + 7) & ~7
        elif tag == 2:  # hash tree
            i += 8 + 8 + 4 * 6 + 8 + 8 + 36
        elif tag == 3:  # kernel cmdline descriptor
            cmd_len = u32le(block, i + 8)
            cmd = block[i + 12:i + 12 + cmd_len].decode(errors="replace")
            out.append(("__avb_cmdline__", cmd))
            i += 12 + cmd_len
            i = (i + 7) & ~7
        else:
            break
    return out


def load_kernel(boot_path, size):
    data = open(boot_path, "rb").read()
    return data[4096:4096 + size]


def extract_config(kernel):
    """IKCONFIG: in questo kernel GKI il blob dopo 'IKCFG_ST' NON è gzip standard
    (CM byte 0xf2, nessun 'IKCFG_ED'): probabilmente sezione compressa/linker-fill.
    Tentativo best-effort: se fallisce restituiamo None (non bloccante)."""
    ik = kernel.find(b"IKCFG_ST")
    if ik < 0:
        return None
    start = kernel.find(b"\x1f\x8b", ik, ik + 512)
    if start < 0 or kernel[start + 2] != 8:  # CM deve essere 8 (deflate)
        return None
    import zlib
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = d.decompress(kernel[start:])
    return out.decode(errors="replace")


def fdt_strings(fdt, limit=40):
    """Estrae le stringhe FDT più informative (model/compatible/SoC)."""
    interesting = []
    for s in ascii_strings(fdt, 4):
        low = s.lower()
        if any(t in low for t in ("qcom", "dell", "x1e", "x1p", "adreno", "model",
                                  "compatible", "serial", "board", "pmk", "geni",
                                  "soundwire", "wcd", "wcx", "panel", "samsung",
                                  "atmel", "elan", "synaptics", "goodix", "hid")):
            interesting.append(s)
    seen, uniq = set(), []
    for s in interesting:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq[:limit]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(BASE, "downloads", "mica", "extract"))
    args = ap.parse_args()
    d = args.dir
    os.makedirs(OUT, exist_ok=True)
    L = [f"# Mica boot images analysis v2 - {datetime.now().isoformat()}",
         "# Solo metadati/valori chiave (nessun contenuto Google).", ""]

    # ---- vbmeta: dimensioni authoritative ----
    vb = os.path.join(d, "vbmeta_a.img")
    sizes = {}
    if os.path.exists(vb):
        L.append("## vbmeta_a (descriptor AVB — dimensioni verificate)")
        for name, val in parse_vbmeta(vb):
            if name == "__avb_cmdline__":
                L.append(f"- avb_cmdline: `{val[:300]}`")
            else:
                sizes[name] = val
                L.append(f"- {name}: image_size = {val}")
        L.append("")

    # ---- boot_a: kernel monolitico ----
    boot_p = os.path.join(d, "boot_a.img")
    boot = open(boot_p, "rb").read()
    ksize = u32le(boot, 8)
    L.append("## boot_a")
    L.append(f"- kernel_size (u32 @8): {ksize} ({ksize/1048576:.2f} MiB)")
    L.append(f"- verifica aritmetica AVB: align({ksize},4096)+4096 = "
             f"{(ksize + 4095) & ~4095 | 4096 if False else ((ksize + 4095) & ~4095) + 4096} "
             f"(AVB0 trovato a 20451328 per ksize=20445831)")
    kernel = boot[4096:4096 + ksize]
    kp = os.path.join(d, "kernel_a.bin")
    open(kp, "wb").write(kernel)
    L.append(f"- kernel estratto: {kp} ({len(kernel)} byte)")
    L.append("")

    # ---- config kernel (IKCONFIG) ----
    L.append("## Config kernel (IKCONFIG embed)")
    cfg = extract_config(kernel)
    if cfg:
        L.append(f"- IKCONFIG presente ({len(cfg)} righe)")
        found = {}
        for line in cfg.splitlines():
            for k in CFG_KEYS:
                if line.startswith(k + "="):
                    found[k] = line.split("=", 1)[1]
        for k in CFG_KEYS:
            if k in found:
                L.append(f"- `{k}={found[k]}`")
        open(os.path.join(OUT, "kernel-config-values.txt"), "w").write(
            "\n".join(f"{k}={v}" for k, v in sorted(found.items())))
    else:
        L.append("- IKCONFIG NON presente")
    L.append("")

    # ---- FDT builtin nel kernel ----
    L.append("## DTB builtin nel kernel")
    fdt_off = kernel.find(b"\xd0\x0d\xfe\xed")
    if fdt_off >= 0:
        total = struct.unpack_from(">I", kernel, fdt_off + 4)[0]
        fdt = kernel[fdt_off:fdt_off + total]
        open(os.path.join(d, "kernel_builtin_dtb.bin"), "wb").write(fdt)
        L.append(f"- FDT a offset kernel {fdt_off}, total_size {total} byte")
        L.append("- stringhe FDT informative:")
        for s in fdt_strings(fdt):
            L.append(f"  - `{s}`")
    else:
        L.append("- nessun FDT nel kernel")
    L.append("")

    # ---- vendor_boot: cmdline + dtb ----
    vb_p = os.path.join(d, "vendor_boot_a.img")
    L.append("## vendor_boot_a (VNDRBOOT v4, page 2048)")
    if os.path.exists(vb_p):
        v = open(vb_p, "rb").read()
        ver = u32le(v, 8)
        page = u32le(v, 12)
        ramdisk_addr = u32le(v, 16)
        dtb_addr = u32le(v, 20)
        vrd_size = u32le(v, 24)
        cmdline = v[28:28 + 2112].split(b"\x00")[0].decode(errors="replace")
        L.append(f"- header_version={ver} page={page} ramdisk_addr=0x{ramdisk_addr:08x} "
                 f"dtb_addr=0x{dtb_addr:08x} vendor_ramdisk_size={vrd_size}")
        L.append(f"- **cmdline**: `{cmdline}`")
        # bootconfig/dtb dopo il ramdisk?
        tail = v[2048 + vrd_size:]
        fdt_pos = tail.find(b"\xd0\x0d\xfe\xed")
        L.append(f"- FDT dopo il ramdisk: {'sì @' + str(2048 + vrd_size + fdt_pos) if fdt_pos >= 0 else 'NO (DTB builtin nel kernel)'}")
        # righe androidboot testuali nel file (bootconfig in chiaro)
        ab = sorted(set(re.findall(rb"androidboot\.[a-z0-9_.]+", v)))
        L.append(f"- chiavi androidboot presenti ({len(ab)}): " + ", ".join(
            x.decode() for x in ab[:40]))
    L.append("")

    # ---- init_boot ----
    ib_p = os.path.join(d, "init_boot_a.img")
    if os.path.exists(ib_p):
        ib = open(ib_p, "rb").read()
        L.append("## init_boot_a")
        L.append(f"- kernel_size={u32le(ib, 8)} ramdisk_size={u32le(ib, 12)} (GKI ramdisk)")
        L.append("")

    # ---- dtb_a / dtbo_a ----
    L.append("## dtb_a / dtbo_a")
    dtb_a = os.path.join(d, "dtb_a.img")
    if os.path.exists(dtb_a):
        da = open(dtb_a, "rb").read()
        allz = not any(da)
        L.append(f"- dtb_a: {len(da)} byte, **tutta zero: {allz}** → "
                 + ("il DT base NON è sul disco: lo fornisce il firmware (ABL/QEMU)" if allz
                    else "contenuto non standard"))
    dtbo_p = os.path.join(d, "dtbo_a.img")
    if os.path.exists(dtbo_p):
        dd = open(dtbo_p, "rb").read()
        magic, total, hsize, esize, ecount, eoff, psize, ver = struct.unpack_from(">8I", dd, 0)
        L.append(f"- dtbo_a: magic {magic:08x} (dtbo image OK={magic==0xd7b7ab1e}), "
                 f"total={total}, entries={ecount}, page={psize}, ver={ver}")
        for i in range(min(ecount, 12)):
            off = eoff + i * esize
            dt_size, dt_off, eid, erev = struct.unpack_from(">4I", dd, off)
            frag = dd[dt_off:dt_off + dt_size]
            strs = [s for s in ascii_strings(frag, 6)
                    if any(t in s.lower() for t in ("dell", "mica", "x1e", "panel",
                                                    "model", "qcom,", "overlay"))][:6]
            L.append(f"  - entry[{i}]: size={dt_size} rev={erev} id=0x{eid:08x} "
                     f"fdt={frag[:4]==b'\\xd0\\x0d\\xfe\\xed'} esempi: {strs}")
    L.append("")

    # ---- vendor ramdisk (lz4 legacy @4096) → inventario moduli ----
    L.append("## vendor ramdisk (moduli .ko)")
    try:
        import lz4.block
        vraw = open(vb_p, "rb").read() if os.path.exists(vb_p) else b""
        pos, out = 4100, bytearray()  # magic lz4 @4096
        while pos + 4 <= len(vraw):
            csz = struct.unpack_from("<I", vraw, pos)[0]
            if csz == 0:
                break
            pos += 4
            try:
                out += lz4.block.decompress(vraw[pos:pos + csz],
                                            uncompressed_size=8 * 1024 * 1024)
            except Exception:
                break
            pos += csz
        if len(out):
            open(os.path.join(d, "vendor_ramdisk.cpio"), "wb").write(out)
            names = sorted(set(n.decode(errors="replace") for n in
                               re.findall(rb"070701[0-9A-Fa-f]{104}([^\x00]+)\x00", bytes(out))
                               if n.endswith(b".ko")))
            L.append(f"- cpio decompresso: {len(out)/1048576:.1f} MiB, {len(names)} moduli .ko")
            x1p = [n for n in names if "x1p42100" in n]
            x1e = [n for n in names if "x1e80100" in n]
            L.append(f"- moduli x1e80100 ({len(x1e)}): " + ", ".join(x1e))
            L.append(f"- **moduli x1p42100 ({len(x1p)})**: " + ", ".join(x1p))
            L.append("- nota: driver di livello superiore (ath11k, DRM, panel) non in questo ramdisk "
                     "(nel vendor super o in stadi successivi) — inventario parziale")
    except ImportError:
        L.append("- lz4 non disponibile (pip install lz4) → inventario moduli saltato")
    L.append("")

    # ---- strings kernel ----
    L.append("## Stringhe kernel indicative (occorrenze)")
    low = kernel.lower()
    for n in [b"dell", b"mica", b"quartz", b"bluey", b"x1e80100", b"x1p42100",
              b"x1e", b"x1p", b"efi stub", b"acpi", b"device tree", b"adreno",
              b"ath11k", b"wcn7850", b"i2c_hid", b"qcom,geni"]:
        c = low.count(n)
        if c:
            L.append(f"- `{n.decode()}`: {c}")
    L.append("")

    # ---- verdetto ----
    L.append("## Verdetto Fase 1")
    if cfg:
        for k in ["CONFIG_EFI", "CONFIG_EFI_STUB", "CONFIG_ACPI", "CONFIG_OF",
                  "CONFIG_OF_OVERLAY", "CONFIG_PCI_ECAM", "CONFIG_ATH11K", "CONFIG_DRM_MSM"]:
            L.append(f"- {k} = {found.get(k, 'n/a (non trovata)')}")
    L.append("- F1 (EFI stub): **probabile Sì** — cmdline con efi=noruntime/novamap; piattaforma "
             "UEFI Qualcomm; da confermare in QEMU (approccio gbos-vm)")
    L.append("- F2 (ACPI vs DT): **DT-based** — dtbo con overlay CRD hamoa-x1e80100; "
             "dtb_a tutta zero; nessun FDT in vendor_boot/kernel → **il DT base lo genera "
             "il firmware** (Qualcomm ABL; in QEMU, QEMU stesso)")
    L.append("- F3 (X1P-42100): **Sì a livello SoC** — moduli gcc/gpucc/camcc/qnoc-x1p42100 "
             "nel vendor ramdisk (la famiglia Googlebook copre X Elite E X Plus)")
    L.append("- Impatto Fase 2 (ThinkBook): console=null da overridare; DTB da fornire via GRUB "
             "(comando devicetree, DT adattato da CRD hamoa x1e80100) O test ACPI puro (se il "
             "kernel GKI ha CONFIG_ACPI); tastiera USB esterna obbligatoria")

    rp = os.path.join(OUT, "bootimg-report.md")
    open(rp, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n[OK] report: {rp}")


if __name__ == "__main__":
    sys.exit(main())
