#!/usr/bin/env bash
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
D=../../downloads/tools/erofs-1.9.4/bin/dump.erofs
IMG=system-port/system.orig.erofs
for f in /system/fonts/NotoColorEmoji.ttf /system/fonts/NotoColorEmojiFlags.ttf /system/fonts/NotoSansCJK-Regular.ttc /system/fonts/NotoSerifCJK-Regular.ttc /system/usr/icu/icudt76l.dat /system/usr/icu/icudt77l.dat /system/usr/icu/icudt75l.dat; do
  echo "--- $f"
  $D --path=$f "$IMG" 2>&1 | grep -E "^Size|regular" | head -2
done
