#!/usr/bin/env bash
# Test discriminante: kernel mica via EFI stub su QEMU virt (AAVMF).
# GRUB legge i file da un disco NVME (AAVMF non ha stack USB),
# l'immagine USB completa e' attaccata anche come usb-storage per il probe.
# Il grub.cfg di test NON ha devicetree: il DT di virt arriva dal firmware,
# quindi se il kernel parte il probe scrive il log -> il boot EFI mica funziona.
set -uo pipefail
W=/home/zero89/gbos-usb
cd "$W"

export LD_LIBRARY_PATH="$W/prefix/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"
GDIR="$W/prefix/usr/lib/grub/arm64-efi"

# cfg di test: cmdline da $1 (default: set completo), DT di virt generata da QEMU
# KERNELBIN: kernel da usare (default: mica; override: Ubuntu generic per confronto)
KERNELBIN="${KERNELBIN:-$W/esp/gbos/kernel.bin}"
CMDLINE="${1:-rdinit=/probe printk.devkmsg=on ignore_loglevel panic=10 panic_print=1 maxcpus=1 earlycon=efi nokaslr console=ttyAMA0}"
rm -rf memdisk-test; mkdir -p memdisk-test/boot/grub
cat > memdisk-test/boot/grub/grub.cfg <<CFG
set default=0
set timeout=1
search --no-floppy --set=root --label GRUBTEST
menuentry 'GBOS EFI-stub test (virt DT)' {
    linux /gbos/kernel.bin $CMDLINE
    devicetree /gbos/virt.dtb
    initrd /gbos/initrd-probe.cpio.gz
}
CFG
timeout 10 qemu-system-aarch64 -M virt -cpu cortex-a76 -m 2G -machine dumpdtb="$W/virt.dtb" -nographic >/dev/null 2>&1 || true
ls -la "$W/virt.dtb"
tar -cf memdisk-test.tar -C memdisk-test boot
"$W/prefix/usr/bin/grub-mkimage" -O arm64-efi -d "$GDIR" \
  -m memdisk-test.tar -o "$W/BOOTAA64-TEST.EFI" \
  -p '(memdisk)/boot/grub' \
  linux fdt gzio normal part_msdos fat configfile echo ls boot memdisk tar search search_label

# ESP di test: EFI/BOOT + kernel + virt DT + initrd
"$W/prefix/usr/bin/mformat" -i "$W/esp-test.img" -C -T 524288 -h 255 -s 63 -v GRUBTEST
mkdir -p "$W/esp-test/EFI/BOOT" "$W/esp-test/gbos"
cp "$W/BOOTAA64-TEST.EFI" "$W/esp-test/EFI/BOOT/BOOTAA64.EFI"
cp "$KERNELBIN" "$W/esp-test/gbos/kernel.bin"
cp "$W/esp/gbos/initrd-probe.cpio.gz" "$W/virt.dtb" "$W/esp-test/gbos/"
"$W/prefix/usr/bin/mcopy" -i "$W/esp-test.img" -s "$W/esp-test/EFI" "::EFI"
"$W/prefix/usr/bin/mcopy" -i "$W/esp-test.img" -s "$W/esp-test/gbos" "::gbos"

# immagine MBR per il disco NVME di test
python3 - "$W/esp-test.img" "$W/nvme-test.img" <<'PY'
import struct, sys
esp, out = sys.argv[1], sys.argv[2]
esp_d = open(esp, 'rb').read()
p1_lba, p1_cnt = 2048, 524288
mbr = bytearray(512)
mbr[446] = 0x80
mbr[446 + 4] = 0x0C
struct.pack_into('<II', mbr, 446 + 8, p1_lba, p1_cnt)
mbr[510:512] = b'\x55\xaa'
with open(out, 'wb') as f:
    f.write(mbr)
    f.seek(p1_lba * 512); f.write(esp_d)
PY

# copia fresca del disco USB per non inquinare usbdisk.img
cp -f "$W/usbdisk.img" "$W/test-disk.img"

echo "=== run AAVMF: GRUB -> kernel mica via EFI stub ==="
timeout 420 qemu-system-aarch64 -M virt -cpu cortex-a76 -m 2G \
  -nographic -bios "$W/efi-prefix/usr/share/AAVMF/AAVMF_CODE.fd" \
  -drive if=none,file="$W/nvme-test.img",format=raw,id=nv \
  -device nvme,drive=nv,serial=GBOSTEST \
  -device qemu-xhci,id=xhci \
  -device usb-storage,bus=xhci.0,drive=u0 \
  -drive if=none,file="$W/test-disk.img",format=raw,id=u0,cache=unsafe \
  2>&1 | tr -d '\033' | sed 's/\[[0-9;]*[A-Za-z]//g' | grep -aE 'GRUB|GBOS|EFI stub|Linux|probe|sda|panic|Run|power|reboot|Booting' | head -30
echo "=== BOOTLOG ==="
"$W/prefix/usr/bin/mcopy" -i "test-disk.img@@269484032" ::/gbos-probe.log /home/zero89/probe-efi.log 2>&1 && head -12 /home/zero89/probe-efi.log
