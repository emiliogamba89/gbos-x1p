#!/usr/bin/env bash
# Bootstrap toolchain per la build Mesa-VirGL (guest Android) su WSL arm64.
# Nessun sudo: meson/ninja da release, bison/flex da sorgenti col clang nativo.
set -eu
WORK=/home/zero89/gbos-build
mkdir -p "$WORK"/{downloads,src,build,tools,bin,guest/mesa-runtime}
cd "$WORK"

echo "=== 1. meson (python puro, eseguito con python3)"
if [ ! -x "$WORK/bin/meson" ]; then
  curl -sL -o downloads/meson.tar.gz https://github.com/mesonbuild/meson/releases/download/1.5.2/meson-1.5.2.tar.gz
  tar -xzf downloads/meson.tar.gz -C src
  cat > bin/meson << EOF
#!/bin/sh
exec python3 $WORK/src/meson-1.5.2/meson.py "\$@"
EOF
  chmod +x bin/meson
fi
"$WORK/bin/meson" --version

echo "=== 2. ninja (binario aarch64 statico)"
if [ ! -x "$WORK/bin/ninja" ]; then
  curl -sL -o /tmp/ninja.zip https://github.com/ninja-build/ninja/releases/download/v1.12.1/ninja-linux-aarch64.zip
  python3 -c "import zipfile; zipfile.ZipFile('/tmp/ninja.zip').extractall('$WORK/bin')"
  chmod +x "$WORK/bin/ninja"
fi
"$WORK/bin/ninja" --version

echo "=== 3. bison 3.8.2 da sorgenti (clang nativo)"
if [ ! -x "$WORK/tools/bison/bin/bison" ]; then
  curl -sL -o downloads/bison.tar.xz https://ftp.gnu.org/gnu/bison/bison-3.8.2.tar.xz
  tar -xJf downloads/bison.tar.xz -C src
  (cd src/bison-3.8.2 && CC=/home/zero89/clang-arm64/clang-r584948b/bin/clang \
    ./configure --prefix=$WORK/tools/bison --disable-nls > build.log 2>&1 \
    && make -j8 >> build.log 2>&1 && make install >> build.log 2>&1) \
    || { tail -20 src/bison-3.8.2/build.log; exit 1; }
fi
"$WORK/tools/bison/bin/bison" --version | head -1

echo "=== 4. flex 2.6.4 da sorgenti"
if [ ! -x "$WORK/tools/flex/bin/flex" ]; then
  curl -sL -o downloads/flex.tar.gz https://github.com/westes/flex/releases/download/v2.6.4/flex-2.6.4.tar.gz
  tar -xzf downloads/flex.tar.gz -C src
  (cd src/flex-2.6.4 && CC=/home/zero89/clang-arm64/clang-r584948b/bin/clang \
    ./configure --prefix=$WORK/tools/flex --disable-nls > build.log 2>&1 \
    && make -j8 >> build.log 2>&1 && make install >> build.log 2>&1) \
    || { tail -20 src/flex-2.6.4/build.log; exit 1; }
fi
"$WORK/tools/flex/bin/flex" --version | head -1

echo "=== 5. mesa 26.2.4 sorgenti"
if [ ! -d "$WORK/src/mesa-26.2.4" ]; then
  curl -sL -o downloads/mesa.tar.xz https://archive.mesa3d.org/mesa-26.2.4.tar.xz
  tar -xJf downloads/mesa.tar.xz -C src
fi
ls "$WORK/src/mesa-26.2.4/subprojects/" | head -6

echo "[OK] bootstrap completo"
