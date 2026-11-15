#!/usr/bin/env bash
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
D=../../downloads/tools/erofs-1.9.4/bin
IMG=../../downloads/mica-16471258/vendor-port/vendor.orig.erofs
$D/dump.erofs --offset=0 --ls --path=/etc/init "$IMG" 2>&1 | tail -60
echo "== hw =="
$D/dump.erofs --offset=0 --ls --path=/etc/init/hw "$IMG" 2>&1 | tail -30
