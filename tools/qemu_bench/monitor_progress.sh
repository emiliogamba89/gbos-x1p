#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== avvio system_server =="
grep -aiE "SystemServer|system_server" "$L" | grep -aiE "Entered|Started|Init|phase|Timeline|boot" | tail -12 | cut -c1-190
echo "== sys.boot_completed / ActivityManager =="
grep -aiE "boot_completed=1|Boot completed|AMS|ActivityManager.*ready|OnBootPhase" "$L" | tail -10 | cut -c1-190
echo "== ultime righe system_server (pid 1442) =="
grep -a " 1442 " "$L" | tail -12 | cut -c1-190
