#!/usr/bin/env bash
set -euo pipefail
# copia gli script dal repo (drxfs) nel fs WSL e lancia il build USB
cp -f /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench/build_usb_test.sh /home/zero89/build_usb_test.sh
cp -f /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench/build_grub_efi.sh /home/zero89/build_grub_efi.sh
cp -f /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench/usb-test/filter_nomap.py /home/zero89/gbos-usb/filter_nomap.py
cp -f /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench/usb-test/probe.c /home/zero89/gbos-usb/probe.c
# anti-cache drxfs: verifica che il copy contenga le modifiche attese
if ! grep -q 'filter_nomap' /home/zero89/build_usb_test.sh; then
    echo "cache drxfs stale: riprovo il copy"
    sleep 3
    cp -f /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench/build_usb_test.sh /home/zero89/build_usb_test.sh
    grep -q 'filter_nomap' /home/zero89/build_usb_test.sh || { echo "ANCORA STALE"; exit 1; }
fi
# sostituisce il richiamo relativo con il path WSL diretto
python3 - <<'PY'
import re
p = '/home/zero89/build_usb_test.sh'
s = open(p).read()
s = re.sub(r'bash "\$\(dirname.*build_grub_efi\.sh"', 'bash /home/zero89/build_grub_efi.sh', s)
open(p, 'w').write(s)
PY
grep -n 'build_grub_efi' /home/zero89/build_usb_test.sh
bash -n /home/zero89/build_usb_test.sh && echo SINTASSI-OK
if bash /home/zero89/build_usb_test.sh > /home/zero89/usb-build.log 2>&1; then
    echo BUILD-OK
else
    echo BUILD-FALLITO:
fi
tail -25 /home/zero89/usb-build.log
echo "=== grub.cfg finale ==="
grep linux /home/zero89/gbos-usb/esp/gbos/grub.cfg
cp /home/zero89/gbos-usb/usbdisk.img /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench/usbdisk.img
echo COPIA-OK
