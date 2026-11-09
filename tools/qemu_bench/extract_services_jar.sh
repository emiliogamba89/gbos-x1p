#!/usr/bin/env bash
# Estrae services.jar dalla partizione system (EROFS) e cerca indizi sul Watchdog
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p
BIN=downloads/tools/erofs-1.9.4/bin
IMG=downloads/mica-16471258/disk-writable.raw
mkdir -p /tmp/sjar
$BIN/dump.erofs "--offset=177209344" --path=/system/framework/services.jar --cat "$IMG" > /tmp/sjar/services.jar 2>/tmp/sjar/err.txt || cat /tmp/sjar/err.txt
ls -la /tmp/sjar/services.jar
# strings nel dex: proprietà e costanti del watchdog
python3 - << 'PYEOF'
import zipfile, re
z = zipfile.ZipFile("/tmp/sjar/services.jar")
names = [n for n in z.namelist() if n.endswith(".dex")]
print("dex files:", names)
data = b"".join(z.read(n) for n in names)
for pat in [rb"watchdog[._a-zA-Z0-9]*", rb"Watchdog[._a-zA-Z0-9]*", rb"monit[a-zA-Z_]*", rb"DEFAULT_TIMEOUT", rb"checkMonitoredThreads"]:
    hits = sorted(set(m.group(0).decode(errors="replace") for m in re.finditer(pat, data)))
    for h in hits[:25]:
        print(pat.decode(), "->", h)
    print()
PYEOF
