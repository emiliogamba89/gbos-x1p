#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
printf 'size=%s\n' "$(stat -c %s "$L" 2>/dev/null || echo 0)"
grep -aiE 'zygote|surfaceflinger|system_server|boot_completed|Watchdog|FATAL EXCEPTION|PackageManager|Too many pending|Kernel panic|GOODBYE' "$L" | tail -35 | cut -c1-200
