#!/usr/bin/env bash
# Lista /etc/vintf/manifest nel vendor pristine
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p
BIN=downloads/tools/erofs-1.9.4/bin
IMG=downloads/mica-16471258/android-desktop_signed_recovery_image.bin
$BIN/dump.erofs "--offset=5647630336" --path=/etc/vintf/manifest --ls "$IMG" 2>&1 | head -60
