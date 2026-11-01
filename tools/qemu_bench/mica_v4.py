#!/usr/bin/env python3
"""Estrazione COMPLETA del recovery mica secondo il layout VNDRBOOT v4
(rispecchia extract_mica_normal.py di gbos-vm, ma in Python puro).

Estrae in downloads/mica/v4/:
  kernel.Image          kernel decompresso (lz4/gzip)
  init_ramdisk.cpio     cpio del ramdisk init_boot
  vendor_N_<tag>.cpio   frammenti vendor_boot con tag dalla vendor_ramdisk_table
  bootconfig.txt        bootconfig incluso nel vendor_boot
  cmdline.txt           cmdline boot_a + vendor_boot combinate
  gpt-parts.json        offset/size delle partizioni chiave (per dump.erofs)

Uso: python tools/qemu_bench/mica_v4.py
"""
import gzip
import json
import os
import struct
import sys
import zlib

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RECOVERY = os.path.join(BASE, "downloads", "mica-16471258", "android-desktop_signed_recovery_image.bin")
OUT = os.path.join(BASE, "downloads", "mica-16471258", "v4")

u = lambda b, o: struct.unpack_from("<I", b, o)[0]
align = lambda n, p: (n + p - 1) // p * p


def lz4_stream(data, pos, end):
    """Decomprime un flusso lz4 legacy (magic gia' consumato) finché dati validi."""
    out = bytearray()
    while pos + 4 <= end:
        csz = struct.unpack_from("<I", data, pos)[0]
        if csz == 0:
            return out, pos + 4
        if csz == 0x184C2102:          # magic del frammento successivo
            return out, pos
        raw = bool(csz & 0x80000000)
        csz &= 0x7FFFFFFF
        pos += 4
        if raw:
            out += data[pos:pos + csz]
        else:
            import lz4.block
            out += lz4.block.decompress(data[pos:pos + csz],
                                        uncompressed_size=256 * 1024 * 1024)
        pos += csz
    return out, pos


def decompress_blob(blob):
    """lz4 legacy o gzip -> dati grezzi."""
    if blob[:2] == b"\x1f\x8b":
        return zlib.decompressobj(31).decompress(blob)
    if blob[:4] == b"\x02\x21\x4c\x18":
        parts, pos = [], 0
        while pos + 4 <= len(blob) and \
                struct.unpack_from("<I", blob, pos)[0] == 0x184C2102:
            part, pos = lz4_stream(blob, pos + 4, len(blob))
            parts.append(part)
        return b"".join(parts)
    return blob


def parse_gpt(f):
    f.seek(512)
    h = f.read(512)
    assert h[:8] == b"EFI PART", "GPT mancante"
    hc = bytearray(h[:u(h, 12)]); hc[16:20] = bytes(4)
    assert zlib.crc32(hc) == u(h, 16), "CRC header GPT"
    lba, count, size = struct.unpack_from("<QII", h, 72)
    f.seek(lba * 512)
    es = f.read(count * size)
    assert zlib.crc32(es) == u(h, 88), "CRC entries GPT"
    parts = {}
    for i in range(count):
        e = es[i * size:(i + 1) * size]
        if not any(e[:16]):
            continue
        name = e[56:128].decode("utf-16le").rstrip("\0")
        s, t = struct.unpack_from("<QQ", e, 32)
        parts[name] = (s * 512, (t + 1) * 512)
    return parts


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not os.path.exists(RECOVERY):
        print("[!] recovery.bin non trovato:", RECOVERY)
        return 1
    os.makedirs(OUT, exist_ok=True)
    manifest = {}

    with open(RECOVERY, "rb") as f:
        parts = parse_gpt(f)
        json.dump({k: list(v) for k, v in parts.items()},
                  open(os.path.join(OUT, "gpt-parts.json"), "w"), indent=1)
        print("[OK] GPT:", len(parts), "partizioni")

        def read_part(n):
            s, t = parts[n]
            f.seek(s)
            return f.read(t - s)

        boot = read_part("boot_a")
        init = read_part("init_boot_a")
        v = read_part("vendor_boot_a")
        assert boot[:8] == init[:8] == b"ANDROID!" and u(boot, 40) == u(init, 40) == 4

        # --- kernel ---
        kernel = boot[4096:4096 + u(boot, 8)]
        kernel = decompress_blob(kernel)
        assert kernel[56:60] == b"ARM\x64", kernel[:64].hex()
        open(os.path.join(OUT, "kernel.Image"), "wb").write(kernel)
        print(f"[OK] kernel.Image: {len(kernel)} byte, magic ARM64")

        # marker IKCFG nel kernel
        m = kernel.find(b"IKCFG_ST")
        if m >= 0:
            try:
                cfg = zlib.decompressobj(31).decompress(kernel[m + 8:])
                open(os.path.join(OUT, "kernel.config"), "wb").write(cfg)
                print(f"[OK] kernel.config estratto ({len(cfg)} byte)!!")
                txt = cfg.decode(errors="replace")
                for key in ("CONFIG_EFI_STUB", "CONFIG_ACPI", "CONFIG_RD_LZ4",
                            "CONFIG_KVM", "CONFIG_VIRTIO_PCI", "CONFIG_VIRTIO_BLK"):
                    line = next((l for l in txt.splitlines() if l.startswith(key + "=")), None)
                    if line:
                        print("   ", line)
            except Exception as e:
                print("[i] IKCFG non decompressibile:", e)

        # --- init_ramdisk ---
        i = 4096 + align(u(init, 8), 4096)
        init_rd = decompress_blob(init[i:i + u(init, 12)])
        open(os.path.join(OUT, "init_ramdisk.cpio"), "wb").write(init_rd)
        print(f"[OK] init_ramdisk.cpio: {len(init_rd)} byte")

        # --- vendor_boot VNDRBOOT v4 completo ---
        assert v[:8] == b"VNDRBOOT" and u(v, 8) == 4
        page, vs = u(v, 12), u(v, 24)
        hs, dtb = u(v, 2096), u(v, 2100)
        ts, count, es, bs = struct.unpack_from("<IIII", v, 2112)
        start = align(hs, page)
        table = start + align(vs, page) + align(dtb, page)
        print(f"[i] VNDRBOOT v4: page={page} ramdisk={vs} hdr={hs} dtb={dtb} "
              f"table@{table} (ts={ts} n={count} es={es} bootconfig={bs})")
        info = []
        for j in range(count):
            e = v[table + j * es: table + (j + 1) * es]
            size, off, kind = struct.unpack_from("<III", e)
            name = e[12:44].split(b"\0")[0].decode() or "platform"
            frag = v[start + off:start + off + size]
            cpio = decompress_blob(frag)
            fn = f"vendor_{j}_{name}"
            open(os.path.join(OUT, fn + ".cpio"), "wb").write(cpio)
            info.append({"file": fn, "kind": kind, "bytes": len(frag),
                         "cpio": len(cpio)})
            print(f"[OK] frammento {j}: tag='{name}' kind={kind} "
                  f"{size} -> cpio {len(cpio)}")
        json.dump(info, open(os.path.join(OUT, "fragments.json"), "w"), indent=1)

        if bs:
            bc = v[table + align(ts, page): table + align(ts, page) + bs]
            open(os.path.join(OUT, "bootconfig.txt"), "wb").write(bc)
            print(f"[OK] bootconfig.txt: {bs} byte")

        # --- cmdline: boot_a @44 + vendor_boot @28 ---
        cmd_boot = boot[44:1580].split(b"\0")[0].decode(errors="replace")
        cmd_vendor = v[28:2076].split(b"\0")[0].decode(errors="replace")
        open(os.path.join(OUT, "cmdline.txt"), "w").write(
            cmd_boot + "\n" + cmd_vendor + "\n")
        print("\n=== cmdline boot_a ===\n" + cmd_boot)
        print("\n=== cmdline vendor_boot ===\n" + cmd_vendor)

        # offset per l'estrazione moduli virtio da system_dlkm (dump.erofs in WSL)
        for name in ("system_dlkm_a", "system_a", "vendor_a"):
            if name in parts:
                print(f"[i] {name}: offset={parts[name][0]} size={parts[name][1]-parts[name][0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
