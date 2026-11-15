#!/usr/bin/env bash
set -u
sleep "${1:-0}"
ps -eo pid=,comm= | grep -i qemu || true
LOG=/home/zero89/qemu-serial-live.log
stat -c '%s bytes, modified %y' "$LOG"
grep -aE 'avb_handle|HASHTREE disabled|verity|FEC|VM-SYSTEM|zz-vm|boot_completed|Kernel panic|Failed to mount /system|avb_slot_verify' "$LOG" | tail -60
tail -12 "$LOG"
