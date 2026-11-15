#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
{
echo "== marker system =="
grep -a "VM-SYSTEM-BUILD4-MARKER" "$L" | head -3
echo "== azioni/parse con righe 60-99 di audioserver.rc =="
grep -aE "audioserver\.rc:(6[0-9]|7[0-9]|8[0-9]|9[0-9])" "$L" | head -5
echo "== zz-vm-fixes: $(grep -ac 'zz-vm-fixes' "$L") =="
echo "== stop eseguiti finora =="
grep -aE "Command .stop " "$L" | grep -av QMI_FW | tail -6
echo "== righe log: $(wc -l < "$L") kernel: $(grep -aoE '^\[ +[0-9]+\.' "$L" | tail -1)"
} 2>&1
