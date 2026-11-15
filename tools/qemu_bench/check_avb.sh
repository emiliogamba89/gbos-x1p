#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
{
echo "== messaggi avb/verity del boot corrente =="
grep -aE "libfs_avb|verity|avb" "$L" | grep -av QMI_FW | head -20
echo
echo "== flags vbmeta su disco (riletta) =="
python3 - <<'EOF'
import struct
f = open("/home/zero89/disk-run.raw", "rb")
for name, off in (("vbmeta_a", 13061062656), ("vbmeta_b", 13065256960)):
    f.seek(off)
    magic = f.read(4)
    f.seek(off + 120)
    flags = struct.unpack("<Q", f.read(8))[0]
    print(f"{name}: magic={magic} flags={flags}")
EOF
} 2>&1
