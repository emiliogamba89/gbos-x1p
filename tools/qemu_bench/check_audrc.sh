#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
{
echo "== parse di audioserver.rc e azioni con line-number =="
grep -a "audioserver.rc" "$L" | grep -av QMI_FW | grep -aE "Parsing|processing action|Command|failed|Parse" | head -12
echo
echo "== quante azioni sul trigger audioserver=running =="
grep -ac "processing action (init.svc.audioserver=running)" "$L"
echo
echo "== errori parse =="
grep -aE "ParseTriggers|unterminated|failed to parse|Invalid" "$L" | head -8
echo
echo "== stato svc audioserver (ultimi cambi di stato) =="
grep -a "init.svc.audioserver" "$L" | grep -av QMI_FW | tail -6
} 2>&1
