#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
bash "$HERE/stop_qemu.sh"
python3 - "$HERE" <<'PY'
import sys,struct,os
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from system_port import crc32c
from extend_system_lp import lp_extents
raw=Path('/home/zero89/disk-run.raw')
offset,size=lp_extents(raw,'system_a')[0]
for path,base in [(raw,offset),(Path(sys.argv[1])/'system-port/system.new.erofs',0)]:
 with path.open('r+b') as f:
  f.seek(base+1024); block=bytearray(f.read(3072))
  assert block[:4]==bytes.fromhex('e2e1f5e0')
  before=struct.unpack_from('<I',block,4)[0]
  block[4:8]=bytes(4)
  expected=crc32c(block)
  assert before in (expected,expected^0xffffffff), 'Unexpected corruption, abort'
  if before!=expected:
   backup=Path('/home/zero89/avb-backups')/(path.name+'.erofs-crc-before.bin')
   if not backup.exists(): backup.write_bytes(struct.pack('<I',before))
   f.seek(base+1028); f.write(struct.pack('<I',expected)); f.flush(); os.fsync(f.fileno())
  print(path,hex(before),'->',hex(expected))
PY
