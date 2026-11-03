#!/bin/bash
set -e
SH=/home/zero89/ndk/shim/toolchains/llvm/prebuilt/linux-x86_64
mkdir -p "$SH"
ln -sfn /home/zero89/ndk/android-ndk-r27c/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/sysroot "$SH/sysroot"
ln -sfn /tmp/clang-arm64/clang-r584948b/bin "$SH/bin"
ln -sfn /tmp/clang-arm64/clang-r584948b/lib "$SH/lib"
ls -la "$SH/"
