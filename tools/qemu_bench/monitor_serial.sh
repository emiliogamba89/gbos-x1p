#!/usr/bin/env bash
# Monitor della seriale live di QEMU (log su fs nativo WSL)
L=/home/zero89/qemu-serial-live.log
echo "=== size: $(stat -c %s $L 2>/dev/null) ==="
grep -acE "invalid extent" $L 2>/dev/null
grep -acE "GOODBYE" $L 2>/dev/null
grep -aE "Created logical system_a|boringssl_self_test64_vendor.*status|Restarting system|first stage started|Kernel panic|started service 'zygote'|started service 'surfaceflinger'|boot_completed" $L 2>/dev/null | head -8 | cut -c1-140
echo "=== tail ==="
tail -1 $L 2>/dev/null | cut -c1-130
