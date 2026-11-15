#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
{
echo "== Parsing file /system/etc/init: $(grep -ac 'Parsing file /system/etc/init' "$L") righe =="
grep -a "Parsing file /system/etc/init" "$L" | head -6
echo "...ultime:"
grep -a "Parsing file /system/etc/init" "$L" | tail -4
echo
echo "== import falliti/errori parse =="
grep -aE "could not import|Failed to parse|ParseTriggers|unterminated" "$L" | head -8
echo
echo "== tutte le Parsing file (ultimo gruppo) =="
grep -a "Parsing file" "$L" | tail -6
echo
echo "== azioni audioserver.rc processate =="
grep -a "audioserver.rc" "$L" | grep -av QMI_FW | head -6
} 2>&1
