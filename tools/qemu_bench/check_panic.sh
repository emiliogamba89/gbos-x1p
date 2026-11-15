#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
{
echo "== prime 40 righe =="
head -40 "$L"
echo
echo "== ultime init prima del panic =="
grep -aE "init:|libfs|verity|avb" "$L" | head -20
} 2>&1
