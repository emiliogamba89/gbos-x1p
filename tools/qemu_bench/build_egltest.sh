#!/usr/bin/env bash
# build della sonda EGL per il guest (aarch64 Android)
set -eu
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
~/tc/w-clang -fPIC -O2 -pie -o /tmp/vm-egltest vm-egltest.c -llog -ldl
cp /tmp/vm-egltest ../../downloads/cuttlefish/extract/swiftshader/vm-egltest
~/clang-arm64/clang-r584948b/bin/llvm-readelf -d /tmp/vm-egltest | grep NEEDED
echo "[OK] egltest costruito"
