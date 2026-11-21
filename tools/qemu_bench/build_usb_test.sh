#!/usr/bin/env bash
# Costruisce la USB di test GBOS: GRUB arm64 + kernel mica + DTB + initrd probe.
set -euo pipefail
W=/home/zero89/gbos-usb
SRC=/mnt/c/Users/emili/Desktop/gbos-x1p
V4="$SRC/downloads/mica-16471258/v4"
RAW="$SRC/downloads/mica-16471258/android-desktop_signed_recovery_image.bin"
mkdir -p "$W/prefix" "$W/esp/gbos"

echo "== [1] DTB = mainline Lenovo ThinkBook 16 (x1p42100) =="
if [ -s "$W/dtb-lenovo.dtb" ]; then
  cp "$W/dtb-lenovo.dtb" "$W/esp/gbos/dtb-lenovo.dtb"
  ls -la "$W/esp/gbos/dtb-lenovo.dtb"
else
  echo "DTB Lenovo assente: esegui prima build_dtb_lenovo.sh" >&2
  exit 1
fi

echo "== [1b] nodo ramoops nel DTB (pstore console per diagnostica panic) =="
FDT="$W/prefix/usr/bin/fdtput"
if [ ! -x "$FDT" ]; then
  cd "$W"
  ls device-tree-compiler_*.deb >/dev/null 2>&1 || apt download device-tree-compiler >/dev/null 2>&1 || true
  dpkg-deb -x device-tree-compiler_*_arm64.deb "$W/prefix"
fi
DTB="$W/esp/gbos/dtb-lenovo.dtb"
"$FDT" -c "$DTB" /reserved-memory/ramoops@c0000000
"$FDT" -t x "$DTB" /reserved-memory/ramoops@c0000000 reg - 0x0 0xc0000000 0x0 0x100000
"$FDT" -t s "$DTB" /reserved-memory/ramoops@c0000000 compatible ramoops
"$FDT" -t u "$DTB" /reserved-memory/ramoops@c0000000 record-size 4096 console-size 131072 ftrace-size 0 pmsg-size 4096 ecc-size 4096

echo "== [1c] no-map -> nomap-off (regioni firmware Dell/XBL/Gunyah inutili su ThinkBook) =="
# le regioni no-map (gunyah-hyp, xbl, aop, cpucp, tme, uefi-log...) stanno a
# inizio RAM (0x80000000-0x81d00000); il kernel GKI da 42MB caricato da
# GRUB/EFI-stub puo' sovrapporvisi: la linear map le salta -> crash silenzioso
# prima del primo printk. Per il probe restano riservate MA mappate.
"$W/prefix/usr/bin/dtc" -I dtb -O dts "$DTB" 2>/dev/null > "$W/dtb-nomap.dts"
python3 "$SRC/tools/qemu_bench/usb-test/filter_nomap.py" "$W/dtb-nomap.dts" "$W/dtb-clean.dts"
"$W/prefix/usr/bin/dtc" -I dts -O dtb -o "$DTB" "$W/dtb-clean.dts" 2>&1 | grep -v Warning || true
"$W/prefix/usr/bin/dtc" -I dtb -O dts "$DTB" 2>/dev/null | grep -c 'nomap-off;'
"$W/prefix/usr/bin/dtc" -I dtb -O dts "$DTB" 2>/dev/null | grep -A3 'ramoops@'

echo "== [2] scarico/estraggo i tool (senza root) =="
cd "$W"
for p in grub-common grub-efi-arm64-bin mtools device-tree-compiler cpio; do
  ls "${p}_"*.deb >/dev/null 2>&1 || apt download "$p" >/dev/null 2>&1 || true
done
ls -la *.deb
for p in grub-common grub-efi-arm64-bin mtools device-tree-compiler cpio; do
  dpkg-deb -x "${p}_"*_arm64.deb "$W/prefix" 2>/dev/null || true
done
export PATH="$W/prefix/usr/bin:$PATH"
export LD_LIBRARY_PATH="$W/prefix/usr/lib/aarch64-linux-gnu:$W/prefix/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"

echo "== [3] probe init statico =="
gcc -O2 -static -o "$W/esp/gbos/probe" "$SRC/tools/qemu_bench/usb-test/probe.c" \
  2>&1 | grep -E 'error|Error' || true
ls -la "$W/esp/gbos/probe"

echo "== [4] initrd probe (cpio.gz, generato con cpio reale) =="
rm -rf "$W/initrd-tree"; mkdir -p "$W/initrd-tree"
cp "$W/esp/gbos/probe" "$W/initrd-tree/probe"
chmod 755 "$W/initrd-tree/probe"
cd "$W/initrd-tree"
mkdir -p dev proc sys tmp log
find . | "$W/prefix/usr/bin/cpio" -o -H newc --owner=0:0 2>/dev/null \
  | gzip -6 > "$W/esp/gbos/initrd-probe.cpio.gz"
ls -la "$W/esp/gbos/initrd-probe.cpio.gz"

echo "== [5] kernel + grub.cfg =="
cp "$V4/kernel.Image" "$W/esp/gbos/kernel.bin"
cat > "$W/esp/gbos/grub.cfg" <<'CFG'
set default=0
set timeout=1
search --no-floppy --set=root --label GRUB
menuentry 'GBOS bring-up probe (mica/ThinkBook)' {
    linux /gbos/kernel.bin rdinit=/probe printk.devkmsg=on ignore_loglevel panic=10 panic_print=1 maxcpus=1 earlycon=efi nokaslr
    devicetree /gbos/dtb-lenovo.dtb
    initrd /gbos/initrd-probe.cpio.gz
}
CFG

echo "== [6] GRUB core image (via build_grub_efi.sh) =="
mkdir -p "$W/esp/EFI/BOOT"
bash "$(dirname "$(readlink -f "$0")")/build_grub_efi.sh"
ls -la "$W/esp/EFI/BOOT/BOOTAA64.EFI"

echo "== [7] FAT images (ESP 256MiB + BOOTLOG 1GiB) =="
"$W/prefix/usr/bin/mformat" -i "$W/esp.img" -C -T 524288 -h 255 -s 63 -v GRUB
"$W/prefix/usr/bin/mcopy" -i "$W/esp.img" -s "$W/esp/EFI" "::EFI"
"$W/prefix/usr/bin/mcopy" -i "$W/esp.img" -s "$W/esp/gbos" "::gbos"
"$W/prefix/usr/bin/mdir" -i "$W/esp.img" ::/ | head -8
"$W/prefix/usr/bin/mformat" -i "$W/log.img" -C -T 2097152 -h 255 -s 63 -v BOOTLOG

echo "== [8] usbdisk.img (MBR: p1 ESP 256MiB, p2 BOOTLOG 1GiB) =="
python3 - "$W/esp.img" "$W/log.img" "$W/usbdisk.img" <<'PY'
import struct, sys
esp, logf, out = sys.argv[1], sys.argv[2], sys.argv[3]
esp_d = open(esp, 'rb').read()
log_d = open(logf, 'rb').read()
p1_lba, p1_cnt = 2048, 524288
p2_lba = p1_lba + p1_cnt
p2_cnt = (len(log_d) + 511) // 512
total = p2_lba + p2_cnt
mbr = bytearray(512)
mbr[446] = 0x80
mbr[446 + 4] = 0x0C
struct.pack_into('<II', mbr, 446 + 8, p1_lba, p1_cnt)
mbr[462 + 4] = 0x0B
struct.pack_into('<II', mbr, 462 + 8, p2_lba, p2_cnt)
mbr[510:512] = b'\x55\xaa'
with open(out, 'wb') as f:
    f.write(mbr)
    f.seek(p1_lba * 512); f.write(esp_d)
    f.seek(p2_lba * 512); f.write(log_d)
print('usbdisk.img:', total * 512, 'byte (p1', p1_cnt, 'sect, p2', p2_cnt, 'sect)')
PY
ls -la "$W/usbdisk.img"
echo "FATTO. Prossimo passo: scrittura su PhysicalDrive2 (richiede UAC)."
