#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== riga boot_completed esatta =="
grep -an "sys.boot_completed=1" "$L" | head -3
grep -an "sys.boot_completed" "$L" | head -5
echo "== contesto =="
grep -aB2 -aA4 "sys.boot_completed=1" "$L" | head -20 | cut -c1-200
echo "== timeline zygote kill =="
grep -an "SIGKILL to service 'zygote'" "$L"
echo "== avvio attuale system_server =="
grep -an "Entered the Android system server" "$L"
