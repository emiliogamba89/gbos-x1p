#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== GOODBYE: $(grep -ac GOODBYE "$L") =="
echo "== morte di 1348 (tra 22:59 e 23:07) =="
grep -aE '22:59|23:0[0-7]' "$L" | grep -aiE 'FATAL|Fatal signal|SIGABRT|SIGSEGV|has died|died|CRASH|Exception|killed|watchdog|OOM' | grep -av QMI_FW | head -25 | cut -c1-220
echo "== init: system_server service events =="
grep -aE "init:.*(system_server|zygote).*(died|exited|SIGKILL|started)" "$L" | tail -8 | cut -c1-200
