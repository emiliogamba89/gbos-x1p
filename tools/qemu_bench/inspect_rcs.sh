#!/usr/bin/env bash
for f in etc/init/hlosminkdaemon.rc etc/init/qseecomd.rc etc/init/android.hardware.weaver-service.android-desktop.rc; do
  echo "=== $f"; head -16 /tmp/rcdump/$f 2>/dev/null
done
