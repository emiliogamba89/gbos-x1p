#!/usr/bin/env bash
# Ripristina il disco scrivibile dall'immagine recovery ufficiale.
# Eseguire soltanto con QEMU spento e dopo backup del disco.
set -euo pipefail
src=/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/android-desktop_signed_recovery_image.bin
dst=/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/disk-writable.raw
[[ -f "$src" && -f "$dst" ]]
[[ "$(stat -c %s "$src")" == "$(stat -c %s "$dst")" ]]
if pgrep -x qemu-system-aarch64 >/dev/null; then
  echo 'ERRORE: QEMU è attivo; non modifico il disco.' >&2
  exit 1
fi
cp --sparse=always "$src" "$dst"
sync
python3 - "$src" "$dst" <<'PY'
import hashlib,sys
h=[]
for p in sys.argv[1:]:
    d=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): d.update(b)
    h.append(d.hexdigest())
print('SHA256 recovery:',h[0])
print('SHA256 disk:    ',h[1])
if h[0]!=h[1]: raise SystemExit('ERRORE: immagini diverse')
print('[OK] disco ripristinato byte-per-byte')
PY
