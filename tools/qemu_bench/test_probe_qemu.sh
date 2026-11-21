#!/usr/bin/env bash
set -uo pipefail
W=/home/zero89/gbos-usb
K=/home/zero89/downloads/mica-16471258/v4/kernel.Image
[ -f "$K" ] || K=/home/zero89/gbos-usb/esp/gbos/kernel.bin
cd "$W"
timeout 150 qemu-system-aarch64 \
  -M virt -cpu cortex-a76 -m 2G \
  -kernel "$K" \
  -initrd "$W/esp/gbos/initrd-probe.cpio.gz" \
  -append "rdinit=/probe console=ttyAMA0 ignore_loglevel" \
  -device qemu-xhci,id=xhci \
  -device usb-storage,bus=xhci.0,drive=usb0 \
  -drive if=none,file="$W/usbdisk.img",format=raw,id=usb0,cache=unsafe \
  -nographic 2>&1 | tail -60
echo "=== QEMU uscito ==="
# se il log è stato scritto nell'immagine, estrailo e mostralo
ls -la /home/zero89/gbos-probe.log 2>/dev/null || true
