#!/usr/bin/env bash
set -u
cd /mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/v4 || exit 1
for k in CONFIG_EFI CONFIG_EFI_STUB CONFIG_ACPI CONFIG_VFAT_FS CONFIG_FAT_FS \
         CONFIG_DRM_SIMPLEDRM CONFIG_FB_EFI CONFIG_DEVTMPFS CONFIG_DEVTMPFS_MOUNT \
         CONFIG_BLK_DEV_INITRD CONFIG_RD_GZIP CONFIG_USB_STORAGE CONFIG_USB_XHCI_HCD \
         CONFIG_USB_XHCI_PCI CONFIG_USB_UAS CONFIG_USB CONFIG_EXFAT_FS CONFIG_MSDOS_FS \
         CONFIG_MODULE_COMPRESS_ZSTD CONFIG_MODULES; do
  v=$(grep -E "^$k=" kernel.config | head -1)
  printf '%-28s %s\n' "$k" "${v:-n/-}"
done
echo "=== moduli nell initrd platform ==="
python3 - <<'PY'
import gzip, io, struct, sys
def read_cpio(path):
    out = []
    with open(path, 'rb') as f:
        data = f.read()
    views = []
    if data[:2] == b'\x1f\x8b':
        try:
            data = gzip.decompress(data)
        except Exception:
            pass
    # newc parser, also handles trailing concatenation
    pos = 0
    while pos + 6 <= len(data):
        magic = data[pos:pos+6]
        if magic != b'070701':
            # try gzip at this position (concatenated gzip members)
            if data[pos:pos+2] == b'\x1f\x8b':
                try:
                    rest = gzip.decompress(data[pos:])
                    pos_inner = 0
                    while pos_inner + 6 <= len(rest):
                        if rest[pos_inner:pos_inner+6] != b'070701':
                            break
                        namesize = int(rest[pos_inner+94:pos_inner+102], 16)
                        name = rest[pos_inner+110:pos_inner+110+namesize-1].decode()
                        mode = int(rest[pos_inner+14:pos_inner+22], 16)
                        filesize = int(rest[pos_inner+54:pos_inner+62], 16)
                        out.append((name, mode, filesize))
                        pos_inner += 110 + namesize + filesize
                        pos_inner = (pos_inner + 3) & ~3
                    break
                except Exception:
                    break
            break
        namesize = int(data[pos+94:pos+102], 16)
        name = data[pos+110:pos+110+namesize-1].decode()
        mode = int(data[pos+14:pos+22], 16)
        filesize = int(data[pos+54:pos+62], 16)
        out.append((name, mode, filesize))
        pos += 110 + namesize + filesize
        pos = (pos + 3) & ~3
    return out

import os
base = '/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/v4/'
for f in ('vendor_0_platform.cpio', 'init_ramdisk.cpio', '../../mica/payload/initrd.img'):
    p = base + f
    if not os.path.exists(p):
        continue
    names = read_cpio(p)
    hits = [n for n, m, s in names if any(x in n.lower() for x in ('fat', 'nls', 'usb-storage', 'uas', 'xhci', 'simpledrm', 'lib/modules'))]
    print(f'-- {f}: {len(names)} entries')
    for h in hits[:12]:
        print('   ', h)
PY
