#!/usr/bin/env bash
set -euo pipefail
src=/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/mica-16471258/disk-writable.raw
dst=/home/zero89/disk-writable-before-recovery.raw
if [[ ! -e "$dst" ]]; then
  cp --sparse=always "$src" "$dst"
fi
sync
stat -c 'backup=%n size=%s' "$dst"
python3 - "$src" "$dst" <<'PY'
import hashlib,sys
for path in sys.argv[1:]:
    with open(path,'rb') as f: print(path,hashlib.sha256(f.read(1048576)).hexdigest())
PY
