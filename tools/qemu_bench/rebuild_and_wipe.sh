#!/usr/bin/env bash
# ricostruzione vendor con rc servizi-assenti corretti + wipe userdata
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
python3 vendor_port.py --raw ../../downloads/mica-16471258/android-desktop_signed_recovery_image.bin --cf ../../downloads/cuttlefish/extract/security --erofs-bin ../../downloads/tools/erofs-1.9.4/bin 2>&1 | tail -3
python3 wipe_fresh.py 2>&1 | tail -2
