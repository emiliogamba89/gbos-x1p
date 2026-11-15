#!/usr/bin/env bash
# Ripristina il metadata LP pristine (primario + backup) dall'immagine recovery
# originale: annulla ogni estensione LP (extend_system/lp_rebuild).
set -e
cd /mnt/c/Users/emili/Desktop/gbos-x1p
ORIG=downloads/mica-16471258/android-desktop_signed_recovery_image.bin
DST=downloads/mica-16471258/disk-writable.raw

# super_start del disco (GPT): 344064 LBA * 512 = 176160768
SS=176160768

# 1) primary metadata: 64KiB @ SS+12288
dd if=$ORIG of=$DST bs=1 skip=$((SS+12288)) seek=$((SS+12288)) count=65536 2>/dev/null
echo "primary metadata ripristinato"

# 2) backup metadata: cerca il magic 'APL0' (30 50 4c 41) negli ultimi 2MiB
#    della partizione super ORIGINALE dell'immagine recovery e copia 64KiB
#    alla stessa posizione del disco
python3 - << 'PYEOF'
import struct
from pathlib import Path
orig = Path("downloads/mica-16471258/android-desktop_signed_recovery_image.bin")
dst = Path("downloads/mica-16471258/disk-writable.raw")
SS = 176160768
with orig.open("rb") as f:
    # super size originale: dal GPT dell'immagine originale
    f.seek(512)
    h = f.read(92)
    ent_lba, n, esz = struct.unpack_from("<QII", h, 72)
    f.seek(ent_lba * 512)
    entries = f.read(n * esz)
    s_last = None
    for i in range(n):
        e = entries[i * esz:(i + 1) * esz]
        if e[:16] == b"\x00" * 16:
            continue
        name = e[56:128].decode("utf-16-le").rstrip("\x00")
        first, last = struct.unpack_from("<QQ", e, 32)
        if name == "super":
            s_last = last
    end = (s_last + 1) * 512
    print(f"super originale termina a {end}")
    f.seek(end - 2 * 1024 * 1024)
    tail = f.read(2 * 1024 * 1024)
idx = tail.rfind(b"0PLA")
assert idx >= 0, "backup metadata non trovato"
abs_off = end - 2 * 1024 * 1024 + idx
print(f"backup metadata trovato @ {abs_off}")
with orig.open("rb") as a, dst.open("r+b") as b:
    a.seek(abs_off)
    data = a.read(65536)
    b.seek(abs_off)
    b.write(data)
print("[OK] backup metadata ripristinato")
PYEOF
