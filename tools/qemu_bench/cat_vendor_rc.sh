#!/usr/bin/env bash
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
D=../../downloads/tools/erofs-1.9.4/bin
IMG=../../downloads/mica-16471258/vendor-port/vendor.orig.erofs
for f in vendor.qti.cdsprpc-service.rc vendor.qti.adsprpc-guestos-service.rc vendor.qti.audio-adsprpc-service.rc; do
  echo "===== $f ====="
  $D/dump.erofs --offset=0 --path=/etc/init/$f --cat "$IMG" 2>/dev/null | grep -aE "^service|^    class|interface aidl" | head -6
done
