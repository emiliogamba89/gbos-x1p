#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== updatable_crashing =="
grep -a "updatable_crashing" "$L" | tail -6 | cut -c1-190
echo "== exited 4 times (ultimi) =="
grep -a "exited 4 times" "$L" | tail -8 | cut -c1-190
echo "== flags_health_check / rescue =="
grep -aiE "flags_health_check|rescue" "$L" | grep -av QMI_FW | tail -8 | cut -c1-190
