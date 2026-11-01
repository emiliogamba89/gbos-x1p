#!/usr/bin/env bash
# Estrae i moduli virtio firmati dal system_dlkm del recovery mica.
# Non richiede erofs-utils con --offset: taglia l'extent con dd e usa
# dump.erofs standard (Ubuntu) sull'immagine tagliata.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RECOVERY="$HERE/../../downloads/mica-16471258/android-desktop_signed_recovery_image.bin"
V4="$HERE/../../downloads/mica-16471258/v4"

[ -f "$V4/dlkm-offsets.json" ] || { echo "[!] manca $V4/dlkm-offsets.json: lancia prima (su Windows)  python tools/qemu_bench/find_dlkm_offset.py"; exit 1; }

read START SIZE <<< "$(python3 -c "
import json
o,s=json.load(open('$V4/dlkm-offsets.json'))['extents_abs'][0]
assert o % (1024*1024) == 0, 'extent non allineato a 1MiB'
print(o//(1024*1024), (s + 1024*1024 - 1)//(1024*1024))
")"
echo "[i] system_dlkm_a: dd -Mib skip=$START count=$SIZE -> dlkm.erofs"
command -v dump.erofs >/dev/null || { echo "[!] dump.erofs mancante: sudo apt install erofs-utils"; exit 1; }

dd if="$RECOVERY" of="$V4/dlkm.erofs" bs=1M skip="$START" count="$SIZE" status=none
dump.erofs -s "$V4/dlkm.erofs" | head -8 || true

# la dump.erofs di Ubuntu non ha --cat: si estrae tutto con fsck.erofs
mkdir -p "$V4/virtio" "$V4/dlkm-extracted"
fsck.erofs --extract="$V4/dlkm-extracted" --no-preserve "$V4/dlkm.erofs" >/dev/null
cd "$V4/dlkm-extracted/lib/modules"
for m in virtio_pci_legacy_dev.ko virtio_pci_modern_dev.ko virtio_pci.ko \
         virtio_dma_buf.ko virtio_blk.ko virtio_net.ko virtio_console.ko; do
  if [ -f "$m" ]; then
    cp "$m" "$V4/virtio/$m"
    echo "[OK] $m ($(stat -c%s "$V4/virtio/$m") byte)"
  else
    echo "[--] $m non presente nel system_dlkm"
  fi
done
echo "[i] moduli in $V4/virtio/"
