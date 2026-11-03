#!/bin/bash
# Setup shim NDK + toolchain file per build SwiftShader Android arm64 (host aarch64 Linux).
set -e
SH=/home/zero89/ndk/shim/toolchains/llvm/prebuilt/linux-x86_64
CLANG=/home/zero89/clang-arm64/clang-r584948b

# NDK r27c: sysroot (estratto) + source.properties + build/cmake
R27C=/home/zero89/ndk/android-ndk-r27c/android-ndk-r27c
if [ ! -d "$R27C" ]; then
    python3 - << 'PY'
import zipfile
z = zipfile.ZipFile('/home/zero89/ndk/ndk.zip')
names = [n for n in z.namelist() if '/sysroot/' in n or '/build/cmake/' in n or n.endswith('source.properties')]
print('estratti', len(names), 'file dal zip r27c')
z.extractall('/home/zero89/ndk/android-ndk-r27c', members=names)
PY
fi

mkdir -p "$(dirname $SH)"
ln -sfn "$R27C/toolchains/llvm/prebuilt/linux-x86_64/sysroot" "$SH/sysroot"
ln -sfn "$CLANG/bin" "$SH/bin"
ln -sfn "$CLANG/lib" "$SH/lib"
ln -sfn "$CLANG" /home/zero89/ndk/shim/toolchains/llvm/prebuilt/linux-aarch64
ln -sfn "$R27C/build" /home/zero89/ndk/shim/build
cp -f "$R27C/source.properties" /home/zero89/ndk/shim/source.properties

mkdir -p /home/zero89/tc
cat > /home/zero89/tc/ndk-shim.cmake << 'CMK'
set(ANDROID_NDK /home/zero89/ndk/shim CACHE PATH "" FORCE)
set(ANDROID_ABI arm64-v8a CACHE STRING "" FORCE)
set(ANDROID_PLATFORM android-35 CACHE STRING "" FORCE)
set(CMAKE_ASM_COMPILER /home/zero89/clang-arm64/clang-r584948b/bin/clang CACHE FILEPATH "" FORCE)
set(CMAKE_C_COMPILER /home/zero89/clang-arm64/clang-r584948b/bin/clang CACHE FILEPATH "" FORCE)
set(CMAKE_CXX_COMPILER /home/zero89/clang-arm64/clang-r584948b/bin/clang++ CACHE FILEPATH "" FORCE)
include(/home/zero89/ndk/android-ndk-r27c/android-ndk-r27c/build/cmake/android.toolchain.cmake)
set(CMAKE_HAVE_LIBC_PTHREAD TRUE CACHE INTERNAL "")
set(CMAKE_USE_PTHREADS_INIT 1 CACHE INTERNAL "")
set(Threads_FOUND TRUE CACHE INTERNAL "")
CMK
echo "shim OK: $SH"
