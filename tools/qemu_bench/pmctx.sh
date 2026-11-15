#!/usr/bin/env bash
# trova gli offset binari di per_mgr nel vendor.erofs e stampa il contesto
IMG=/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/vendor-port/vendor.orig.erofs
grep -aob "per_mgr" "$IMG" | cut -d: -f1 > /tmp/pm_off.txt
while read -r off; do
  echo "=== offset $off ==="
  dd if="$IMG" bs=1 skip=$((off-400)) count=900 2>/dev/null | tr -c "[:print:]\n" " "
  echo
done < /tmp/pm_off.txt
