#!/usr/bin/env python3
"""FASE 1 - Download e prima analisi del recovery ufficiale "mica" (Dell XPS Googlebook).

>>> Nessun file derivato dal recovery va committato: solo i report testuali. <<<

Uso:
    python tools/fetch_mica.py --list          # mostra il catalogo recovery Google
    python tools/fetch_mica.py                 # download + verifica MD5 + estrazione + dump GPT
    python tools/fetch_mica.py --skip-download # riusa recovery.zip/bin gia' scaricati
    python tools/fetch_mica.py --delete-zip    # libera lo zip dopo l'estrazione del .bin

Comportamento:
  1. legge il catalogo ufficiale (dl.google.com/.../production_recovery.json),
     seleziona il device "mica" e mostra build/URL/MD5;
  2. scarica recovery.zip (~7.1 GiB) verificando l'MD5 in streaming;
  3. estrae l'immagine GPT (~17.9 GiB) e verifica l'MD5 anche di questa
     (il catalogo non specifica se l'MD5 si riferisce a zip o bin: proviamo tutti e
     due e il report dichiara quale combacia);
  4. scrive reports/mica-analysis/gpt.txt (tabella partizioni, committabile);
  5. estrae le partizioni piccole (boot/vendor_boot/vbmeta/init_boot, slot a/b)
     in downloads/mica/extract/ come .img pronti per unpack_bootimg (Fase 1).

Solo stdlib (funziona da Windows/WSL/Linux). Serve ~30 GB liberi; consigliato
--out verso un disco locale veloce (di default va in downloads/mica del progetto).
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import zipfile
from datetime import datetime
from urllib.request import urlopen

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_URL = "https://dl.google.com/dl/edgedl/device/recovery/production_recovery.json"
DEVICE = "mica"
CHUNK = 1024 * 1024
# partizioni da estrarre per l'analisi kernel (se presenti nel GPT)
KEY_PARTS = ["boot_a", "boot_b", "vendor_boot_a", "vendor_boot_b",
             "init_boot_a", "init_boot_b", "vbmeta_a", "vbmeta_b",
             "vendor_kernel_boot_a", "vendor_kernel_boot_b",
             "dtb_a", "dtb_b", "dtbo_a", "dtbo_b"]
MAX_EXTRACT_SIZE = 512 * 1024 * 1024  # sicurezza: nessuna partizione piu' grande

GPT_TYPES = {
    "C12A7328-F81F-11D2-BA4B-00A0C93EC93B": "EFI System",
    "E6D6D379-F507-44C2-A23C-238F2A3DF928": "Linux x86 root",
    "0FC63DAF-8483-4772-8E79-3D69D8477DE4": "Linux filesystem",
    "EBD0A0A2-B9E5-4433-87C0-68B6B72699C7": "Microsoft basic data",
    "21686148-6449-6E6F-744E-656564454649": "BIOS boot",
}


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def fetch_catalog():
    print(f"[*] Catalogo recovery: {CATALOG_URL}")
    with urlopen(CATALOG_URL, timeout=60) as r:
        cat = json.loads(r.read().decode())
    return cat


def pick(cat, device):
    for e in cat:
        if e.get("device") == device:
            return e
    raise SystemExit(f"[!] device '{device}' non trovato nel catalogo")


def download(url, dest, expected_md5=None):
    """Download streaming con MD5 progressivo e barra di stato in MB."""
    part = dest + ".part"
    if os.path.exists(dest):
        print(f"[*] {dest} esiste gia': verifica MD5 ...")
        got = md5_file(dest)
        if expected_md5 and got != expected_md5:
            print(f"[!] MD5 non corrisponde ({got} != {expected_md5}): ridownload")
        else:
            print("    MD5 ok, skip download")
            return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with urlopen(url, timeout=120) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length", 0)) or None
        h = hashlib.md5()
        done = 0
        print(f"[*] download {url}")
        while True:
            b = r.read(CHUNK)
            if not b:
                break
            f.write(b)
            h.update(b)
            done += len(b)
            if total:
                print(f"\r    {done/1048576:8.0f} / {total/1048576:.0f} MiB", end="")
            else:
                print(f"\r    {done/1048576:8.0f} MiB", end="")
        print()
    got = h.hexdigest()
    if expected_md5 and got != expected_md5:
        os.remove(part)
        raise SystemExit(f"[!] MD5 NON valido: {got} != {expected_md5} (download rimosso)")
    os.replace(part, dest)
    print(f"    MD5 ok ({got}) -> {dest}")
    return dest


def extract_bin(zip_path, out_dir):
    """Estrae il membro piu' grande (l'immagine GPT) dal recovery.zip."""
    with zipfile.ZipFile(zip_path) as z:
        infos = sorted(z.infolist(), key=lambda i: i.file_size, reverse=True)
        print(f"[*] contenuto di {os.path.basename(zip_path)}:")
        for i in infos:
            print(f"    {i.file_size/1073741824:7.2f} GiB  {i.filename}")
        big = infos[0]
        dest = os.path.join(out_dir, os.path.basename(big.filename))
        if os.path.exists(dest) and os.path.getsize(dest) == big.file_size:
            print(f"[*] immagine gia' estratta: {dest}")
            return dest
        print(f"[*] estrazione {big.filename} ({big.file_size/1073741824:.2f} GiB) ...")
        with z.open(big) as src, open(dest, "wb") as f:
            done = 0
            while True:
                b = src.read(CHUNK)
                if not b:
                    break
                f.write(b)
                done += len(b)
                print(f"\r    {done/1073741824:6.2f} GiB", end="")
        print()
        return dest


def parse_gpt(path):
    """Parser GPT minimale (nessuna dipendenza). Ritorna lista di dict.
    Nota: l'header GPT non contiene la sector size; si assume 512B (standard
    per i recovery Google; anche gbrunch richiede geometria 512B)."""
    SECTOR = 512
    out = []
    with open(path, "rb") as f:
        f.seek(SECTOR)
        hdr = f.read(512)
        if hdr[:8] != b"EFI PART":
            raise SystemExit("[!] il file non e' un'immagine GPT (header 'EFI PART' mancante)")
        entry_lba = struct.unpack_from("<Q", hdr, 72)[0]
        num = struct.unpack_from("<I", hdr, 80)[0]
        esz = struct.unpack_from("<I", hdr, 84)[0]
        for i in range(num):
            f.seek(entry_lba * SECTOR + i * esz)
            e = f.read(esz)
            if e[:16] == b"\x00" * 16:
                continue
            first, last = struct.unpack_from("<Q", e, 32)[0], struct.unpack_from("<Q", e, 40)[0]
            name = e[56:128].decode("utf-16-le").rstrip("\x00")
            # type GUID: primi 3 campi little-endian, ultimi 2 gruppi big-endian
            a, b_, c_ = struct.unpack("<IHH", e[0:8])
            g = e[8:16]
            tguid = f"{a:08X}-{b_:04X}-{c_:04X}-{g[0:2].hex().upper()}-{g[2:8].hex().upper()}"
            out.append({"n": i + 1, "name": name, "type": tguid, "first": first, "last": last})
    return out, SECTOR


def gpt_report(entries, sector, path, md5s, cat_entry):
    lines = []
    lines.append(f"# Mica recovery GPT analysis - {datetime.now().isoformat()}")
    lines.append(f"# file: {os.path.basename(path)}")
    lines.append(f"# build: {cat_entry['buildidentifier']}  branch: {cat_entry.get('branch','')}")
    lines.append(f"# md5 catalogo: {cat_entry['md5']}")
    lines.append(f"# md5 zip:  {md5s.get('zip')}")
    lines.append(f"# md5 bin:  {md5s.get('bin')}")
    lines.append(f"# MATCH catalogo: {md5s.get('match', 'NESSUNO?!')}")
    lines.append("")
    lines.append(f"{'#':>2}  {'nome':<20} {'tipo':<22} {'inizio(LBA)':>12} {'fine(LBA)':>12} {'size':>10}")
    for e in entries:
        size = (e["last"] - e["first"] + 1) * sector
        tname = GPT_TYPES.get(e["type"], e["type"])
        lines.append(f"{e['n']:>2}  {e['name']:<20} {tname:<22} {e['first']:>12} {e['last']:>12} {size/1048576:>7.1f}Mi")
    return "\n".join(lines) + "\n"


def extract_key_parts(entries, sector, bin_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    names = [e["name"] for e in entries]
    wanted = [n for n in KEY_PARTS if n in names]
    print(f"[*] estrazione partizioni chiave: {', '.join(wanted) or 'NESSUNA trovata!'}")
    for n in wanted:
        e = next(x for x in entries if x["name"] == n)
        size = (e["last"] - e["first"] + 1) * sector
        if size > MAX_EXTRACT_SIZE:
            print(f"    [skip] {n}: {size/1048576:.0f} MiB > limite")
            continue
        dest = os.path.join(out_dir, f"{n}.img")
        with open(bin_path, "rb") as f, open(dest, "wb") as o:
            f.seek(e["first"] * sector)
            remaining = size
            while remaining > 0:
                b = f.read(min(CHUNK, remaining))
                if not b:
                    break
                o.write(b)
                remaining -= len(b)
        print(f"    {n}.img ({size/1048576:.1f} MiB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="mostra il catalogo ed esce")
    ap.add_argument("--skip-download", action="store_true", help="usa file gia' scaricati")
    ap.add_argument("--extract-only", action="store_true",
                    help="riusa l'immagine estratta: solo GPT + estrazione partizioni (no MD5 lunghe)")
    ap.add_argument("--delete-zip", action="store_true", help="cancella lo zip dopo l'estrazione")
    ap.add_argument("--out", default=os.path.join(BASE, "downloads", DEVICE))
    ap.add_argument("--pin-gbos-vm", action="store_true",
                    help="scarica il build 16471258 pinato di gbos-vm (super con il "
                         "sistema incluso) invece dell'ultimo build del catalogo")
    args = ap.parse_args()

    if args.pin_gbos_vm:
        args.out = os.path.join(BASE, "downloads", f"mica-{PIN_BUILD}")
        os.makedirs(args.out, exist_ok=True)
        zip_path = os.path.join(args.out, "recovery.zip")
        bin_path = os.path.join(args.out, "android-desktop_signed_recovery_image.bin")
        if args.skip_download or os.path.exists(bin_path):
            print(f"[*] pinato: uso {bin_path}")
        else:
            download(PIN_URL, zip_path, expected_sha256=PIN_ZIP_SHA256)
            bin_path = extract_bin(zip_path, args.out)
            got = sha256_file(bin_path)
            if got != PIN_BIN_SHA256:
                raise SystemExit(f"[!] SHA256 immagine: {got} != {PIN_BIN_SHA256}")
            print("[OK] immagine pinata verificata (sha256 ok)")
        print("[OK] ora: mica_v4.py + build_initrd_v3.py + extract_virtio.sh (vedi QEMU-BENCH.md)")
        return 0

    cat = fetch_catalog()
    if args.list:
        for e in cat:
            print(f"{e['device']:<10} {e['manufacturer']:<8} {e['buildidentifier']:<32} "
                  f"{e['filesize']/1073741824:6.2f} GiB  md5={e['md5']}")
        return 0
    ent = pick(cat, DEVICE)
    if not args.extract_only:
        print(f"[*] device '{DEVICE}': {ent['model']} | build {ent['buildidentifier']} | "
              f"branch {ent.get('branch','')} | {ent['filesize']/1073741824:.2f} GiB | md5 {ent['md5']}")

    os.makedirs(args.out, exist_ok=True)
    rep_dir = os.path.join(BASE, "reports", "mica-analysis")
    os.makedirs(rep_dir, exist_ok=True)

    zip_path = os.path.join(args.out, "recovery.zip")
    bin_path = os.path.join(args.out, "android-desktop_signed_recovery_image.bin")
    if args.extract_only:
        if not os.path.exists(bin_path):
            raise SystemExit(f"[!] --extract-only richiede {bin_path} gia' estratto")
    else:
        if not args.skip_download:
            download(ent["url"], zip_path, ent["md5"] if ent.get("md5") else None)
        else:
            print(f"[*] --skip-download: uso {zip_path}")
        bin_path = extract_bin(zip_path, args.out)

    print("[*] calcolo MD5 (zip e immagine) per identificare quale combacia col catalogo ...")
    md5s = {"zip": md5_file(zip_path), "bin": md5_file(bin_path)}
    target = ent["md5"].lower()
    if md5s["zip"] == target:
        md5s["match"] = "ZIP"
    elif md5s["bin"] == target:
        md5s["match"] = "BIN (immagine)"
    else:
        md5s["match"] = "NESSUNO - ATTENZIONE, file non corrispondente al catalogo!"
        print(f"[!] {md5s['match']}")

    print("[*] analisi GPT ...")
    entries, sector = parse_gpt(bin_path)
    if args.extract_only:
        report = gpt_report(entries, sector, bin_path, {"zip": "-", "bin": "-", "match": "- (extract-only)"}, ent)
    else:
        print("[*] calcolo MD5 (zip e immagine) per identificare quale combacia col catalogo ...")
        md5s = {"zip": md5_file(zip_path) if os.path.exists(zip_path) else "-", "bin": md5_file(bin_path)}
        target = ent["md5"].lower()
        if md5s["zip"] == target:
            md5s["match"] = "ZIP"
        elif md5s["bin"] == target:
            md5s["match"] = "BIN (immagine)"
        else:
            md5s["match"] = "NESSUNO - ATTENZIONE, file non corrispondente al catalogo!"
            print(f"[!] {md5s['match']}")
        report = gpt_report(entries, sector, bin_path, md5s, ent)
    rp = os.path.join(rep_dir, "gpt.txt")
    with open(rp, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"[OK] report GPT: {rp}")

    extract_key_parts(entries, sector, bin_path, os.path.join(args.out, "extract"))

    if args.delete_zip:
        os.remove(zip_path)
        print(f"[*] zip rimosso: {zip_path}")

    print("\n[OK] Prossimo passo (Fase 1): unpack_bootimg su")
    print(f"     {os.path.join(args.out, 'extract')}/*.img  -> EFI stub? ACPI o DTB? cmdline?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
