#!/usr/bin/env bash
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
D=../../downloads/tools/erofs-1.9.4/bin
echo "== vm-absent-hardware.rc scritto nel vendor.erofs locale =="
$D/dump.erofs --offset=0 --path=/etc/init/vm-absent-hardware.rc --cat ../../downloads/mica-16471258/vendor-port/vendor.erofs 2>/dev/null | head -40
