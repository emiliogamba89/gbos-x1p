#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "GOODBYE count: $(grep -aicE 'GOODBYE' "$L")"
echo "boot_completed hits: $(grep -aicE 'sys.boot_completed=1|boot_completed' "$L")"
grep -aiE 'Restart not allowed|not killing|Watchdog' "$L" | grep -av keystore2 | tail -8 | cut -c1-220
echo "--- system_server ---"
grep -aiE "started service 'system_server'|Service 'system_server'.*(pid|received|exited)|starting service 'system_server'" "$L" | tail -8 | cut -c1-220
echo "--- tail ---"
tail -2 "$L" | cut -c1-200
