#!/usr/bin/env bash
set -euo pipefail
cd /mnt/c/Users/emili/Desktop/gbos-x1p
python3 - <<'PY'
import struct,subprocess
from pathlib import Path
b=Path('downloads/tools/erofs-1.9.4/bin/dump.erofs')
for name in ['orig','new']:
 p=Path('tools/qemu_bench/system-port/system.'+name+'.erofs')
 with p.open('rb') as f:
  f.seek(1024); sb=f.read(128)
  bs=1<<sb[12]; meta,xbase=struct.unpack_from('<II',sb,40)
  print(name,'rootnid',struct.unpack_from('<H',sb,14)[0], 'meta',meta,'xbase',xbase)
  for path in ['/','/system','/system/etc/init','/system/framework/services.jar']:
   t=subprocess.check_output([str(b),'--path='+path,str(p)],text=True)
   print(t)
   nid=int(next(l for l in t.splitlines() if l.startswith('NID:')).split()[1])
   off=meta*bs+nid*32; f.seek(off); inode=f.read(128)
   fmt,ic=struct.unpack_from('<HH',inode)
   print('inode',off, 'fmt',fmt,'icount',ic, inode.hex())
PY
