#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== 1213-1214s: azione init del restart =="
grep -aE "\[ *121[3-4]\." "$L" | grep -avE "QMI_FW" | head -25 | cut -c1-210
echo "== chi ha emesso restart zygote (processing action) =="
grep -a "restart" "$L" | grep -a "processing action" | tail -6 | cut -c1-210
echo "== runtime restart / soft reboot di system_server =="
grep -aiE "Runtime restart|runtime_restart|sys.boot_completed|BOOT FAILURE|RescueParty" "$L" | tail -8 | cut -c1-190
