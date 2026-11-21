#!/usr/bin/env bash
set -u
cd /mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/v4 || exit 1
for k in CONFIG_OF CONFIG_OF_EARLY_FLATTREE CONFIG_ACPI CONFIG_EFI_STUB CONFIG_FB_SIMPLE CONFIG_DRM_SIMPLEDRM CONFIG_FONT_SUPPORT CONFIG_FB; do
  printf '%-26s %s\n' "$k" "$(grep -E "^$k=" kernel.config | head -1)"
done
RAW=/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/android-desktop_signed_recovery_image.bin
python3 - "$RAW" <<'PY'
import struct, sys
raw = sys.argv[1]
with open(raw, 'rb') as f:
    f.seek(13153337344)  # boot_a
    d = f.read(8 * 1024 * 1024)
print('boot magic:', d[:8])
if d[:8] == b'ANDROID!':
    hver, ksz, rsz = struct.unpack_from('<III', d, 40)
    page = struct.unpack_from('<I', d, 10 * 4)[0]
    print(f'header_version={hver} kernel_size={ksz} ramdisk_size={rsz} page={page}')
offs = []
i = d.find(b'\xd0\x0d\xfe\xed')
while i >= 0:
    offs.append(i)
    i = d.find(b'\xd0\x0d\xfe\xed', i + 1)
print('DTB magic in boot_a @:', offs[:10])
# cerca anche DTBO table magic 0xd7b7ab1e nel dtbo_a
with open(raw, 'rb') as f:
    f.seek(13298040832)  # dtbo_a
    t = f.read(64)
print('dtbo_a magic:', t[:8].hex(), t[:8])
PY
