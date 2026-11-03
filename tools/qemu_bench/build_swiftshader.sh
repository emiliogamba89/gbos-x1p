#!/bin/bash
# Build SwiftShader (Vulkan ICD) per Android arm64 in WSL2 e copia l'artefatto
# nella cartella cuttlefish del repo, pronta per vendor_port.py.
#
# Contesto: in Android 17 non esiste piu' SwiftShader EGL/GLES; l'unica via
# software e' SwiftShader VULKAN (libvk_swiftshader.so) usato come driver
# ro.hardware.vulkan=swiftshader, con ANGLE (backend vulkan) sopra.
#
# Prerequisiti (una-tantum):
#   1. swiftshader_setup.sh  -> shim NDK aarch64: /home/zero89/ndk/shim +
#      clang CI in /home/zero89/clang-arm64/clang-r584948b + toolchain file
#   2. git clone https://github.com/google/swiftshader ~/swiftshader
#   3. patch Android nel tree (VkDeviceMemoryExternalAndroid etc. — gia' in
#      locale; upstream le compila solo con ANDROID=ON, il fix qui sotto
#      aggiunge solo -landroid -llog che il CMake standalone dimentica)
#
# Note build:
#   - CMAKE_POLICY_VERSION_MINIMUM=3.5: i submoduli vecchi (marl) rompono cmake 4.x
#   - il toolchain file imposta ANDEX abi android-35 con clang CI (host aarch64)
#   - -DSWIFTSHADER_BUILD_TESTS=OFF: submodule googletest non estratto
#
# Uso: bash build_swiftshader.sh  (idempotente)

set -e
SW=~/swiftshader
SB=~/swbuild
TC=/home/zero89/tc/ndk-shim.cmake
DEST=/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/cuttlefish/extract/swiftshader

CMAKE=~/.local/lib/python3.12/site-packages/cmake/data/bin/cmake
NINJA=$(command -v ninja || echo ~/.local/bin/ninja)
# cmake (nel suo re-run interno dopo il cambio compiler) deve trovare ninja nel PATH
export PATH="$HOME/.local/bin:$PATH"
echo "[i] cmake=$CMAKE ninja=$NINJA"

# 0. patch locali al tree (idempotenti):
#    a. ripara eventuali righe stray "android/log" nel CMakeLists di Vulkan
#    b. rimuove -Wl,--no-undefined globale: AHardwareBuffer_createFromHandle non
#       esiste negli stub NDK (c'e' solo in libnativewindow.so reale sul device);
#       il simbolo resta undefined nell'.so e viene risolto a runtime dal loader
#       Android (DT_NEEDED libnativewindow.so garantito da --no-as-needed)
python3 - "$SW/src/Vulkan/CMakeLists.txt" << 'PY'
import sys
p = sys.argv[1]
s = open(p).read()
fixed = s.replace("\n        android\n        log\nset(ROOT_PROJECT_COMPILE_OPTIONS",
                  "\nset(ROOT_PROJECT_COMPILE_OPTIONS")
if fixed != s:
    open(p, "w").write(fixed)
    print("CMakeLists.txt riparato (righe stray rimosse)")
PY
python3 - "$SW/CMakeLists.txt" << 'PY'
import sys
p = sys.argv[1]
s = open(p).read()
old = 'APPEND_STRING PROPERTY LINK_FLAGS " -Wl,--no-undefined")'
if old in s:
    open(p, "w").write(s.replace(old, 'APPEND_STRING PROPERTY LINK_FLAGS "")'))
    print("CMakeLists.txt: -Wl,--no-undefined rimosso")
PY

# 0b. wrapper compiler: cmake Android-Clang calcola un triple SENZA API
#     (aarch64-none-linux-android -> crtbegin_dynamic.o non trovato) e il driver
#     clang usa il PRIMO --target della riga: il wrapper quindi FILTRA i
#     --target/--sysroot ricevuti e re-inietta quelli giusti in coda
WRAP=/home/zero89/tc
REAL=/home/zero89/clang-arm64/clang-r584948b
SYSROOT=/home/zero89/ndk/shim/toolchains/llvm/prebuilt/linux-x86_64/sysroot
# STL headers per il modulo Android di cmake (layout NDK classico): se lo shim
# non li ha, estrai dal zip r27c solo la dir llvm-libc++
if [ ! -e /home/zero89/ndk/shim/sources/cxx-stl/llvm-libc++/include ]; then
  # il modulo Android di cmake vuole il layout NDK legacy in sources/: li
  # costruiamo con symlink al sysroot r27c (libc++ merged, abi inclusa)
  mkdir -p /home/zero89/ndk/shim/sources/cxx-stl/llvm-libc++/libs/arm64-v8a
  ln -sfn $SYSROOT/usr/include/c++/v1 \
      /home/zero89/ndk/shim/sources/cxx-stl/llvm-libc++/include
  ln -sfn $SYSROOT/usr/include/c++/v1 \
      /home/zero89/ndk/shim/sources/cxx-stl/llvm-libc++abi/include
  ln -sfn $SYSROOT/usr/lib/aarch64-linux-android/35/libc++.a \
      /home/zero89/ndk/shim/sources/cxx-stl/llvm-libc++/libs/arm64-v8a/libc++_static.a
  ln -sfn $SYSROOT/usr/lib/aarch64-linux-android/35/libc++.so \
      /home/zero89/ndk/shim/sources/cxx-stl/llvm-libc++/libs/arm64-v8a/libc++.so
  echo "albero STL shim creato"
fi
SYSROOT=/home/zero89/ndk/shim/toolchains/llvm/prebuilt/linux-x86_64/sysroot
for lang in clang clang++; do
  cat > "$WRAP/w-$lang" << EOF
#!/bin/bash
args=()
for a in "\$@"; do
  case "\$a" in
    --target=*|--sysroot=*|--gcc-toolchain=*) ;;
    *) args+=("\$a") ;;
  esac
done
exec $REAL/bin/$lang --target=aarch64-none-linux-android35 --sysroot=$SYSROOT "\${args[@]}"
EOF
  chmod +x "$WRAP/w-$lang"
done

# 1. configure (supporto Android nativo di CMake: NIENTE toolchain file, che
#    forza i compiler a meta'-configure e butta la cache; lo shim NDK ha i
#    symlink clang CI + sysroot r27c nelle path standard)
#    NOTA: -Wl,--no-undefined gia' neutralizzato qui sopra (createFromHandle)
"$CMAKE" -S "$SW" -B "$SB" -G Ninja \
    -DCMAKE_SYSTEM_NAME=Android \
    -DCMAKE_ANDROID_NDK=/home/zero89/ndk/shim \
    -DCMAKE_ANDROID_ARCH_ABI=arm64-v8a \
    -DCMAKE_ANDROID_API=35 \
    -DCMAKE_SYSTEM_VERSION=35 \
    -DCMAKE_SYSROOT=$SYSROOT \
    -DCMAKE_C_COMPILER=$WRAP/w-clang \
    -DCMAKE_CXX_COMPILER=$WRAP/w-clang++ \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DCMAKE_BUILD_TYPE=Release \
    -DSWIFTSHADER_BUILD_TESTS=OFF \
    -DSWIFTSHADER_BUILD_PVR=OFF \
    -DSWIFTSHADER_BUILD_BENCHMARKS=OFF \
    -DSWIFTSHADER_WARNINGS_AS_ERRORS=OFF \
    -DCMAKE_SHARED_LINKER_FLAGS="-landroid -lnativewindow -Wl,--no-as-needed"

# 2. build (solo il target ICD: ~10 min su 8 core TCG)
"$NINJA" -C "$SB" vk_swiftshader

ls -la "$SB/Android/"
# 3. copia nel repo (vendor_port.py lo prendera' da qui)
mkdir -p "$DEST"
cp -f "$SB/Android/libvk_swiftshader.so" "$DEST/libvk_swiftshader.so"
echo "[OK] $DEST/libvk_swiftshader.so"
