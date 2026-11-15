#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
python3 "$HERE/test_avb_helpers.py"
python3 "$HERE/dump_vbmeta.py" /home/zero89/vbmeta_a_orig.bin
python3 -m py_compile "$HERE"/{dump_vbmeta,restore_vbmeta_test,dex_checksums,patch_services_v3,system_port,test_avb_helpers}.py
for file in run_qemu stop_qemu rebuild_system_avb_fix repair_services_checksums monitor_avb_test monitor_system_fixes; do
 bash -n "$HERE/$file.sh"
done
# This dry run must fail BEFORE rotating the active QEMU serial log.
before=$(stat -c '%i:%s' /home/zero89/qemu-serial-live.log)
if pgrep -f '^qemu-system-aarch64 ' >/dev/null; then
 if WAIT_SECONDS=1 bash "$HERE/run_qemu.sh" v3 >/home/zero89/qemu-concurrent-guard-test.log 2>&1; then
  echo 'ERROR: concurrent-run guard failed' >&2; exit 1
 fi
 grep 'QEMU aarch64 già attivo' /home/zero89/qemu-concurrent-guard-test.log
 inode=${before%%:*}
 test "$inode" = "$(stat -c '%i' /home/zero89/qemu-serial-live.log)"
fi
