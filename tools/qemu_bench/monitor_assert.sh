#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
line=$(grep -an "Assertion failed: status != NO_ERROR" "$L" | head -1 | cut -d: -f1)
echo "prima occorrenza alla riga $line"
sed -n "$((line-30)),$((line+35))p" "$L" | grep -aE "DEBUG|Abort|#[0-9]+ pc|pid|Cmdline|signal" | head -50 | cut -c1-200
