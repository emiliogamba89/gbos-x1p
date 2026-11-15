#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
bash "$HERE/stop_qemu.sh"
cp /home/zero89/qemu-serial-live.log /home/zero89/qemu-serial-avb-fixed-dex-invalid.log
python3 - "$HERE" <<'PY'
import sys,zipfile
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from dex_checksums import finalize_dex,verify_dex,write_aligned_jar
p=Path('/home/zero89/services-v3.jar')
backup=p.with_name('services-v3-before-checksum-fix.jar')
if not backup.exists(): backup.write_bytes(p.read_bytes())
with zipfile.ZipFile(p) as jar:
 entries={name:jar.read(name) for name in jar.namelist()}
for name,data in entries.items():
 if name.endswith('.dex'):
  print(name, 'before checksums valid:',verify_dex(data))
  entries[name]=finalize_dex(data)
write_aligned_jar(p.with_suffix('.fixed.jar'), entries)
p.with_suffix('.fixed.jar').replace(p)
print('Corrected and verified',p)
PY
bash "$HERE/rebuild_system_avb_fix.sh"
