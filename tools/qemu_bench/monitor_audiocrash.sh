#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== primo backtrace audioserver (40 righe da un Fatal signal) =="
grep -an "Fatal signal" "$L" | grep -a audioserver | head -2
line=$(grep -an "Fatal signal" "$L" | grep -a audioserver | head -1 | cut -d: -f1)
if [ -n "$line" ]; then
  sed -n "${line},$((line+45))p" "$L" | cut -c1-190
fi
