#!/usr/bin/env bash
python3 - <<'PY'
from pathlib import Path
for file,start,end in [('/home/zero89/avb-research/fs_avb.cpp',440,565),('/home/zero89/googlebook_image_rebuilder/builder/lib/devprofile.py',1,280)]:
 print('\nFILE',file)
 for n,line in enumerate(Path(file).read_text().splitlines(),1):
  if start<=n<=end: print(f'{n}: {line}')
PY
