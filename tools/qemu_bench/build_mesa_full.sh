#!/usr/bin/env bash
# Build Mesa VirGL GLES completa (setup + ninja + strip + publish)
# da lanciare dopo il riavvio WSL: una sola riga.
set -eu
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
bash build_mesa_gles.sh
WORK=/home/zero89/gbos-build
BUILD=$WORK/build/mesa-gles
CLANG=/home/zero89/clang-arm64/clang-r584948b/bin
echo "=== ninja build (this takes a while)"
"$WORK/bin/ninja" -j8 -C "$BUILD" > "$WORK/build/mesa-gles.build.log" 2>&1 \
  || { tail -30 "$WORK/build/mesa-gles.build.log"; exit 1; }
tail -3 "$WORK/build/mesa-gles.build.log"
echo "=== strip + publish"
DEST=$WORK/guest/mesa-runtime
mkdir -p "$DEST"
for pair in src/egl/libEGL_virgl.so src/mesa/glapi/es1api/libGLESv1_CM_virgl.so \
            src/mesa/glapi/es2api/libGLESv2_virgl.so \
            src/gallium/targets/dri/libgallium_dri.so \
            subprojects/libdrm-2.4.133/libdrm.so; do
  out="$DEST/$(basename "$pair")"
  "$CLANG/llvm-strip" --strip-unneeded -o "$out" "$BUILD/$pair"
  ls -la "$out"
done
echo "[OK] Mesa VirGL GLES costruita in $DEST"
