#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
{
echo "== pid 875 e 877 e 988 =="
grep -a "has pid 875\|has pid 877\|has pid 988" "$L" | head -6
echo "== azioni vm-absent processate =="
grep -a "vm-absent-hardware.rc" "$L" | head -8
echo "== stop udsattestation eseguito? =="
grep -a "stop udsattestation" "$L" | head -4
echo "== processing action audioserver=running =="
grep -a "processing action (init.svc.audioserver=running)" "$L" | head -4
echo "== morte system_server 1168 =="
grep -a "1168" "$L" | grep -avE "QMI_FW" | tail -6
grep -a "Service 'system_server'\|service .system_server." "$L" | grep -av QMI_FW | tail -4
} 2>&1 | head -60
