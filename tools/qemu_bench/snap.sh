#!/usr/bin/env bash
# Snapshot diagnostico del run corrente su log seriale nativo.
L=/home/zero89/qemu-serial-live.log
O=/tmp/snap.txt
{
echo "== size $(stat -c %s $L) righe $(wc -l < $L) =="
echo "== zz-vm-fixes parse/trigger =="
grep -a "zz-vm-fixes" "$L" | head -6
echo "== comandi stop eseguiti =="
grep -aE "Command .stop (audioserver|android\.system|timberslide|ssgqmigd)" "$L" | tail -8
echo "== per_mgr: $(grep -ac 'vendor.per_mgr' "$L") riferimenti =="
echo "== QMI_FW: $(grep -ac 'QMI_FW' "$L") righe =="
echo "== audioserver SIGSEGV: $(grep -acE 'SIGSEGV.*audioserver|audioserver.*SIGSEGV' "$L") =="
echo "== updatable_crashing: $(grep -ac 'updatable_crashing.1' "$L") =="
echo
echo "== system_server =="
grep -a "Entered the Android system server" "$L" | tail -3
echo
echo "== boot_completed / launcher =="
grep -aiE "boot_completed|sys.boot|Launcher" "$L" | grep -av QMI_FW | tail -6
echo
echo "== morti/kill =="
grep -aE "WATCHDOG KILLING|GOODBYE|Zygote.*died|signal 6|signal 11" "$L" | grep -av QMI_FW | tail -6
echo
echo "== ultime 10 non-QMI =="
grep -av "QMI_FW" "$L" | tail -10
} > "$O" 2>&1
cat "$O"
