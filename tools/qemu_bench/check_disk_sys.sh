#!/usr/bin/env bash
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
BIN=../../downloads/tools/erofs-1.9.4/bin
D=/home/zero89/disk-run.raw
# ricostruisce l'immagine system_a dalle 3 extent
dd if=$D of=/tmp/sys_ext1.img bs=4096 skip=$((177209344/4096)) count=$((1081446400/4096)) status=none
dd if=$D of=/tmp/sys_ext2.img bs=4096 skip=$((8216961024/4096)) count=$((21721088/4096)) status=none
dd if=$D of=/tmp/sys_ext3.img bs=4096 skip=$((8238682112/4096)) count=$((32768/4096)) status=none
cat /tmp/sys_ext1.img /tmp/sys_ext2.img /tmp/sys_ext3.img > /tmp/sys_from_disk.img
ls -la /tmp/sys_from_disk.img
echo "== audioserver.rc dal DISCO (ultime 12 righe) =="
$BIN/dump.erofs --offset=0 --path=/system/etc/init/audioserver.rc --cat /tmp/sys_from_disk.img 2>&1 | tail -12
echo "== e dal system.new.erofs (ultime 12 righe) =="
$BIN/dump.erofs --offset=0 --path=/system/etc/init/audioserver.rc --cat system-port/system.new.erofs 2>&1 | tail -12
