#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
{
echo "== per_mgr nel log (non QMI) =="
grep -a "per_mgr" "$L" | grep -av "QMI_FW" | head -10
echo "== per_mgr in system.orig.erofs =="
grep -ac "per_mgr" /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench/system-port/system.orig.erofs || echo 0
echo "== per_mgr nel kernel/dlkm erofs =="
grep -ac "per_mgr" /mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/v4/dlkm.erofs || echo 0
} 2>&1
