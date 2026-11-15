#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
bash "$HERE/stop_qemu.sh"
cd "$HERE/../.."
cp --sparse=always tools/qemu_bench/system-port/system.new.erofs /home/zero89/system-before-avb-fix.erofs
python3 tools/qemu_bench/system_port.py --patched /home/zero89/services-v3.jar --raw /home/zero89/disk-run.raw --erofs-bin downloads/tools/erofs-1.9.4/bin > /home/zero89/rebuild-system-avb-fix.log 2>&1
tail -15 /home/zero89/rebuild-system-avb-fix.log
