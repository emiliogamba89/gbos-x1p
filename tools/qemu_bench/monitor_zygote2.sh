#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== esattamente attorno a 2763.8 (SIGKILL zygote) =="
grep -aE "\[ *276[2-6]\." "$L" | grep -avE "QMI_FW" | head -30 | cut -c1-230
echo
echo "== seguirne le conseguenze: riavvio zygote/system_server =="
grep -aE "\[ *27[6-9][0-9]\." "$L" | grep -aiE "zygote|system_server" | grep -av QMI_FW | head -15 | cut -c1-210
