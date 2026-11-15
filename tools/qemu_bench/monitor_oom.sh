#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== OOM / memory pressure nel kernel =="
grep -aiE "Out of memory|oom-kill|lowmemorykiller|Killed process|memory cgroup|vm.pressure" "$L" | tail -15 | cut -c1-200
echo "== contesto attorno a 2763s (kill zygote) =="
grep -aE "\[ *27[0-9][0-9]\." "$L" | grep -avE "QMI_FW|logd" | head -25 | cut -c1-200
