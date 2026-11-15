#!/usr/bin/env bash
{
for p in $(ls /proc | grep -E '^[0-9]+$'); do
  if grep -qa "qemu-system" /proc/$p/comm 2>/dev/null; then
    echo "PID $p:"
    tr '\0' '\n' < /proc/$p/cmdline | grep -B1 -A1 "initrd" | head -6
  fi
done
} 2>&1
