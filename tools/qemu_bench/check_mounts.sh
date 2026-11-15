#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
{
echo "== fs_mgr mount / dm setup =="
grep -aE "fs_mgr|libfs_mgr|Mounted|dm-[0-9]|device-mapper|verity|avb|vbmeta|snapshot" "$L" | grep -av "QMI_FW" | head -40
} 2>&1
