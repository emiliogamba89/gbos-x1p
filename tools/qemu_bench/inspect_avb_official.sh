#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import urllib.request,base64,pathlib
root=pathlib.Path('/home/zero89/avb-research'); root.mkdir(exist_ok=True)
urls={
'avbtool.py':'https://android.googlesource.com/platform/external/avb/+/refs/heads/main/avbtool.py?format=TEXT',
'fs_avb.cpp':'https://android.googlesource.com/platform/system/core/+/refs/heads/main/fs_mgr/libfs_avb/fs_avb.cpp?format=TEXT',
}
for name,url in urls.items():
 p=root/name
 if not p.exists(): p.write_bytes(base64.b64decode(urllib.request.urlopen(url,timeout=60).read()))
 print(p)
PY
python3 /home/zero89/avb-research/avbtool.py info_image --image /home/zero89/vbmeta_a_orig.bin
grep -n -E 'DISABLED|digest|verification_disabled|hashtree_disabled' /home/zero89/avb-research/fs_avb.cpp
grep -nE 'avb|vbmeta|update_partition_descriptor' /home/zero89/googlebook_image_rebuilder/builder/lib/devprofile.py
