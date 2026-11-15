#!/usr/bin/env bash
# Ri-estrae services.jar dal disco e applica la patch v3 (NOP kill Watchdog,
# breakCrashLoop, ExternalCaptureStateTracker). Salva il jar in /home/zero89
# (sopravvive ai wipe di /tmp) e lo usa per ricostruire system su disk-run.raw.
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
BIN=/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/tools/erofs-1.9.4/bin
ORIG=/mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench/system-port/system.orig.erofs
mkdir -p /tmp/sjar3
"$BIN/dump.erofs" --offset=0 --path=/system/framework/services.jar --cat "$ORIG" > /tmp/sjar3/services.jar
ls -la /tmp/sjar3/services.jar
python3 patch_services_v3.py /tmp/sjar3/services.jar /tmp/sjar3/services-v3.jar
cp /tmp/sjar3/services-v3.jar /home/zero89/services-v3.jar
echo "[*] ricostruzione system su disk-run.raw..."
python3 system_port.py --patched /tmp/sjar3/services-v3.jar --raw /home/zero89/disk-run.raw --erofs-bin ../../downloads/tools/erofs-1.9.4/bin 2>&1 | grep -vE '^\[cmd\]' | tail -8
