#!/usr/bin/env bash
# Mesa 26.2.4 VirGL GLES per Android aarch64 — variante WSL della ricetta gbos-vm
# (build-guest.sh upstream; differenze: clang arm64 nativo + sysroot shim, no darwin).
set -eu
WORK=/home/zero89/gbos-build
MESA=$WORK/src/mesa-26.2.4
BUILD=$WORK/build/mesa-gles
CLANG=/home/zero89/clang-arm64/clang-r584948b/bin
SYSROOT=/home/zero89/ndk/shim/toolchains/llvm/prebuilt/linux-x86_64/sysroot
export PATH="$WORK/tools/bison/bin:$WORK/tools/flex/bin:$WORK/bin:$PATH"

echo "=== cross file"
cat > "$WORK/android-aarch64.cross" << EOF
[binaries]
c = ['$CLANG/clang', '--target=aarch64-none-linux-android35', '--sysroot=$SYSROOT']
cpp = ['$CLANG/clang++', '--target=aarch64-none-linux-android35', '--sysroot=$SYSROOT',
       '-fno-exceptions', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
       '-static-libstdc++']
ar = '$CLANG/llvm-ar'
strip = '$CLANG/llvm-strip'
c_ld = 'lld'
cpp_ld = 'lld'
pkg-config = '/usr/bin/pkg-config'
[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'armv8'
endian = 'little'
[properties]
needs_exe_wrapper = true
pkg_config_libdir = '$WORK/android-pkgconfig'
EOF
mkdir -p "$WORK/android-pkgconfig"

echo "=== meson setup"
if [ ! -f "$BUILD/build.ninja" ]; then
  "$WORK/bin/meson" setup "$BUILD" "$MESA" \
    --cross-file "$WORK/android-aarch64.cross" \
    --buildtype=release \
    -Dforce_fallback_for=libdrm,expat \
    -Dallow-fallback-for=libdrm \
    -Dplatforms=android -Dplatform-sdk-version=35 -Dandroid-stub=true \
    -Dandroid-libbacktrace=disabled -Dllvm=disabled -Dglx=disabled -Dgbm=disabled \
    -Dvideo-codecs= -Dgallium-va=disabled -Dzstd=disabled \
    -Dgallium-drivers=virgl -Dvulkan-drivers= \
    -Degl=enabled -Dgles1=enabled -Dgles2=enabled -Dopengl=true \
    -Degl-lib-suffix=_virgl -Dgles-lib-suffix=_virgl \
    > "$WORK/build/mesa-gles.configure.log" 2>&1 \
    || { tail -30 "$WORK/build/mesa-gles.configure.log"; exit 1; }
fi
tail -5 "$WORK/build/mesa-gles.configure.log"
echo "[OK] configurato — pronto per ninja"
