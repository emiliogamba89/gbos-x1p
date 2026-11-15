#!/usr/bin/env bash
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
BIN=../../downloads/tools/erofs-1.9.4/bin
IMG=../../downloads/mica-16471258/vendor-port/vendor.orig.erofs
$BIN/dump.erofs --offset=0 --path=/etc/init/hw/init.target.rc --cat "$IMG" > /tmp/init.target.rc 2>/dev/null
echo "== blocchi per_mgr / per_proxy in init.target.rc =="
grep -n -A8 "^service vendor.per_" /tmp/init.target.rc
echo "== start espliciti in tutti i rc vendor (incl. hw/) =="
$BIN/dump.erofs --offset=0 --ls --path=/etc/init/hw "$IMG" 2>/dev/null | grep -oE "[^ ]+\.rc" | grep -v "^\\.\\." | while read -r f; do
  $BIN/dump.erofs --offset=0 "--path=/etc/init/hw/$f" --cat "$IMG" 2>/dev/null | grep -n "start.*per_mgr\|start.*per_proxy" | sed "s|^|$f:|"
done
grep -n "per_mgr\|per_proxy" /tmp/init.target.rc
