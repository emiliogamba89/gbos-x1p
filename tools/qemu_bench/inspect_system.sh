#!/usr/bin/env bash
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
D=../../downloads/tools/erofs-1.9.4/bin/dump.erofs
IMG=system-port/system.orig.erofs
$D --path=/system/bin/boringssl_self_test64 --cat "$IMG" > /tmp/bst64 2>/dev/null || $D --path=/system/bin/boringssl_self_test --cat "$IMG" > /tmp/bst64 2>/dev/null
ls -la /tmp/bst64
strings -a /tmp/bst64 2>/dev/null | grep -iE "watchdog|self.test|fips|module|hash|integrity|prop|system/framework|services.jar|/system|/vendor|/apex|fail" | sort -u | head -40
