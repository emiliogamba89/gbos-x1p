#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== contesto 1200-1215s =="
grep -aE "\[ *12(0[0-9]|1[0-5])\." "$L" | grep -avE "QMI_FW" | head -45 | cut -c1-200
