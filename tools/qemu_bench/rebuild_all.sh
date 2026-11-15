#!/usr/bin/env bash
# Rebuild completo: vendor (per_mgr disabled, rc ripuliti) + system (jar v3,
# zz-vm-fixes.rc) su disk-run.raw. Lancia run_qemu detached alla fine NO (lo
# fa boot_long.bat da Windows).
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
echo "=== vendor ==="
WRITABLE_PATH=/home/zero89/disk-run.raw python3 vendor_port.py --graphics virgl \
  --raw ../../downloads/mica-16471258/android-desktop_signed_recovery_image.bin \
  --cf ../../downloads/cuttlefish/extract/security \
  --erofs-bin ../../downloads/tools/erofs-1.9.4/bin 2>&1 | tail -4
echo "=== system ==="
python3 system_port.py --patched /tmp/sjar3/services-v3.jar \
  --raw /home/zero89/disk-run.raw \
  --erofs-bin ../../downloads/tools/erofs-1.9.4/bin 2>&1 | grep -vE '^\[cmd\]' | tail -8
