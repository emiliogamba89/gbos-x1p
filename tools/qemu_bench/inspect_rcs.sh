#!/usr/bin/env bash
set -u
RE=/home/zero89/clang-arm64/clang-r584948b/bin/llvm-readelf
for f in libEGL_virgl.so libgallium_dri.so libGLESv2_virgl.so libGLESv1_CM_virgl.so libdrm.so; do
  echo "== $f"
  "$RE" -d "/home/zero89/gbos-build/guest/mesa-runtime/$f" | grep NEEDED
done
