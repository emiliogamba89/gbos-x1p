#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
{
echo "== dal modulo 12 in poi fino al panic =="
grep -an "init:" "$L" | sed -n '12,40p'
} 2>&1
