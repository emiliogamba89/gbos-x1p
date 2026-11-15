#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== dimensione: $(stat -c %s $L) =="
echo "== system_server 1348 (ultime righe) =="
grep -a "1348" "$L" | tail -15 | cut -c1-200
echo "== ActivityManager/ActivityTaskManager recenti =="
grep -aiE "ActivityManager|ActivityTaskManager" "$L" | tail -12 | cut -c1-200
echo "== ultime 8 righe log =="
tail -8 "$L" | cut -c1-200
