#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== dimensioni =="
stat -c '%s byte, modificato %y' "$L"
echo "== GOODBYE =="
grep -ac "GOODBYE" "$L"
echo "== boot_completed =="
grep -aiE "sys.boot_completed=1|Boot completed|boot_completed" "$L" | grep -av "before boot completed" | tail -10 | cut -c1-200
echo "== SystemUI / Launcher / Home =="
grep -aiE "SystemUI|Launcher|ActivityTaskManager.*startHome|HomeActivity" "$L" | tail -12 | cut -c1-200
echo "== system_server: entered/restarted =="
grep -a "Entered the Android system server" "$L"
echo "== WATCHDOG KILLING =="
grep -a "WATCHDOG KILLING" "$L" | cut -c1-160
echo "== blocchi reportati =="
grep -a "Blocked in" "$L" | cut -c1-180
echo "== zygote SIGKILL / riavvii =="
grep -acE "received SIGKILL" "$L"
echo "== ultime 15 righe =="
tail -15 "$L" | cut -c1-200
