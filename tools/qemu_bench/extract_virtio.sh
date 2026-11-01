#!/usr/bin/env bash
# Estrae i moduli virtio firmati dal system_dlkm del recovery mica.
# Serve dump.erofs (erofs-utils): installare con  sudo apt install erofs-utils
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RECOVERY="$HERE/../../downloads/mica-16471258/android-desktop_signed_recovery_image.bin"
V4="$HERE/../../downloads/mica-16471258/v4"

command -v dump.erofs >/dev/null || { echo "[!] dump.erofs mancante: sudo apt install erofs-utils"; exit 1; }
[ -f "$V4/gpt-parts.json" ] || { echo "[!] lancia prima mica_v4.py (su Windows)"; exit 1; }

OFF=$(python3 -c "import json;print(json.load(open('$V4/gpt-parts.json'))['system_dlkm_a'][0])")
echo "[i] system_dlkm_a @ offset $OFF"
mkdir -p "$V4/virtio"

for m in virtio_pci_legacy_dev.ko virtio_pci_modern_dev.ko virtio_pci.ko \
         virtio_dma_buf.ko virtio_blk.ko virtio_net.ko virtio_console.ko; do
  if dump.erofs --offset="$OFF" --path="/lib/modules/$m" --cat "$RECOVERY" \
      > "$V4/virtio/$m" 2>/dev/null \
     && [ "$(head -c4 "$V4/virtio/$m")" = "$(printf '\x7fELF')" ]; then
    echo "[OK] $m ($(stat -c%s "$V4/virtio/$m") byte)"
  else
    rm -f "$V4/virtio/$m"
    echo "[--] $m non presente nel system_dlkm"
  fi
done
echo "[i] moduli in $V4/virtio/"
