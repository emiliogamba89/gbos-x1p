#!/usr/bin/env bash
set -u
B=/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/tools/erofs-1.9.4/bin
V=/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/vendor-port/vendor.orig.erofs
rm -rf /tmp/rcdump && mkdir -p /tmp/rcdump && cd /tmp/rcdump
"$B/fsck.erofs" --extract=/tmp/rcdump -d0 "$V" >/dev/null 2>&1
echo "--- rc che invocano logcat:"
grep -rl "logcat" /tmp/rcdump/etc/init/ 2>/dev/null | head -6
grep -rh "logcat" /tmp/rcdump/etc/init/*.rc 2>/dev/null | head -8
