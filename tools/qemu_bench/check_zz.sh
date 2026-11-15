#!/usr/bin/env bash
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
BIN=../../downloads/tools/erofs-1.9.4/bin
IMG=system-port/system.new.erofs
echo "== ls /system/etc/init (ultimi 12) =="
$BIN/dump.erofs --offset=0 --ls --path=/system/etc/init "$IMG" 2>&1 | tail -12
echo "== cat zz-vm-fixes.rc =="
$BIN/dump.erofs --offset=0 --path=/system/etc/init/zz-vm-fixes.rc --cat "$IMG" 2>&1 | head -20
echo "== tar overlay: voci zz =="
tar tvf system-port/overlay.tar | grep -E "zz-vm|etc/init" || echo "NESSUNA voce zz nel tar!"
