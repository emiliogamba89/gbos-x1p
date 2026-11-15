#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== panic/oops gravi =="
grep -aiE "Kernel panic|BUG: kernel|Oops|Watching watchdog threads|bye!:|Restarting system" "$L" | tail -8 | cut -c1-180
echo "== audioserver: SIGSEGV e stops =="
grep -acE "audioserver\), pid" "$L"
grep -aE "init.svc.audioserver" "$L" | tail -5 | cut -c1-180
echo "== zygote/system_server morti? =="
grep -aE "SIGKILL to service 'zygote'|system_server.*Untracked|Entered the Android" "$L" | tail -6 | cut -c1-180
echo "== boot_completed =="
grep -acE "sys.boot_completed=1" "$L"
echo "== bootanim / launcher =="
grep -aiE "bootanim|nexuslauncher|Launcher" "$L" | tail -6 | cut -c1-180
echo "== tail =="
tail -4 "$L" | cut -c1-180
