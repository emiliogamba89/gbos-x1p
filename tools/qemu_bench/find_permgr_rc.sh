#!/usr/bin/env bash
# cerca il rc vendor che definisce per_mgr e mostra il contesto
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
BIN=../../downloads/tools/erofs-1.9.4/bin
IMG=../../downloads/mica-16471258/vendor-port/vendor.orig.erofs
$BIN/dump.erofs --offset=0 --ls --path=/etc/init "$IMG" 2>/dev/null | grep -oE "[^ ]+\.rc" | grep -v "^\.\." | sort -u > /tmp/vrcs.txt
echo "== $(wc -l < /tmp/vrcs.txt) rc vendor =="
while read -r f; do
  c=$($BIN/dump.erofs --offset=0 "--path=/etc/init/$f" --cat "$IMG" 2>/dev/null | grep -c "per_mgr")
  [ "$c" -gt 0 ] && echo ">>> $f ($c occorrenze)" && \
    $BIN/dump.erofs --offset=0 "--path=/etc/init/$f" --cat "$IMG" 2>/dev/null | grep -B2 -A6 "per_mgr"
done < /tmp/vrcs.txt
