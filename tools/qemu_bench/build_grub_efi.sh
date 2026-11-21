#!/usr/bin/env bash
set -euo pipefail
W=/home/zero89/gbos-usb
GDIR=$(ls -d "$W"/prefix/usr/lib/grub/arm64-efi | head -1)
export LD_LIBRARY_PATH="$W/prefix/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"

rm -rf "$W/memdisk"; mkdir -p "$W/memdisk/boot/grub"
cp "$W/esp/gbos/grub.cfg" "$W/memdisk/boot/grub/grub.cfg"
tar -cf "$W/memdisk.tar" -C "$W/memdisk" boot

"$W/prefix/usr/bin/grub-mkimage" -O arm64-efi \
  -d "$GDIR" \
  -m "$W/memdisk.tar" \
  -o "$W/esp/EFI/BOOT/BOOTAA64.EFI" \
  -p '(memdisk)/boot/grub' \
  linux fdt gzio normal part_msdos fat configfile echo ls boot
ls -la "$W/esp/EFI/BOOT/BOOTAA64.EFI"
