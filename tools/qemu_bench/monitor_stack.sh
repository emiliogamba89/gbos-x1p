#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
# blocco completo della stack trace del Watchdog per il main thread
grep -an "GOODBYE" "$L" | head -2
first=$(grep -an "Blocked in" "$L" | head -1 | cut -d: -f1)
if [ -n "$first" ]; then
  sed -n "${first},$((first+8))p" "$L" | cut -c1-200
  echo "..."
fi
# stack del main thread: dalla prima riga Watchdog dopo 'Blocked' fino a GOODBYE
awk '/Blocked in/{found=1} found && /Watchdog:/{print} /GOODBYE/{if(found) exit}' "$L" | head -45 | cut -c1-200
