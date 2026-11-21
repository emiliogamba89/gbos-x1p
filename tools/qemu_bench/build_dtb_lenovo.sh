#!/usr/bin/env bash
set -euo pipefail
W=/home/zero89/gbos-usb
KT=/home/zero89/linux-6.18
cd /home/zero89

if [ ! -d "$KT" ]; then
  if [ ! -f linux-6.18.tar.xz ]; then
    echo "scarico kernel 6.18..."
    wget -q https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.18.tar.xz
  fi
  echo "estrazione selettiva..."
  tar -xf linux-6.18.tar.xz --wildcards \
    'linux-6.18/Makefile' \
    'linux-6.18/arch/arm64/boot/dts/qcom/*' \
    'linux-6.18/arch/arm64/kernel/image.*' \
    'linux-6.18/include/dt-bindings/*' \
    'linux-6.18/include/linux/*' \
    'linux-6.18/scripts/*' \
    'linux-6.18/drivers/clk/qcom/*' \
    'linux-6.18/Kbuild' 'linux-6.18/Kconfig'
  KT=/home/zero89/linux-6.18
fi
ls "$KT/arch/arm64/boot/dts/qcom/" | grep -i thinkbook

echo "== compilo DTB ThinkBook 16 (cpp + dtc, senza kbuild) =="
cd "$KT/arch/arm64/boot/dts/qcom"
if [ ! -x /home/zero89/gbos-usb/prefix/usr/bin/dtc ]; then
  cd /home/zero89/gbos-usb
  ls device-tree-compiler_*.deb >/dev/null 2>&1 || apt download device-tree-compiler >/dev/null 2>&1 || true
  dpkg-deb -x device-tree-compiler_*_arm64.deb /home/zero89/gbos-usb/prefix
  cd "$KT/arch/arm64/boot/dts/qcom"
fi
DTC=$(ls /home/zero89/gbos-usb/prefix/usr/bin/dtc | head -1)
DTS=x1p42100-lenovo-thinkbook-16.dts
INC="-I. -I$KT/include -I$KT/include/dt-bindings -undef -nostdinc -x assembler-with-cpp"
cpp $INC "$DTS" -o /tmp/tb16.dts.tmp
"$DTC" -I dts -O dtb -o "$W/dtb-lenovo.dtb" /tmp/tb16.dts.tmp 2>&1 | grep -v Warning | head -5 || true
ls -la "$W/dtb-lenovo.dtb"
# sanity: compatibile e modello
"$DTC" -I dtb -O dts -o /tmp/tb16-check.dts "$W/dtb-lenovo.dtb" 2>/dev/null
grep -m1 -A2 'qcom,x1p42100' /tmp/tb16-check.dts | head -4
