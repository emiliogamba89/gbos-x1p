#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== attorno al SIGKILL di zygote (2758-2770s) =="
grep -aE "\[ *27(5[5-9]|6[0-9]|7[0-5])\." "$L" | grep -avE "QMI_FW" | head -40 | cut -c1-210
