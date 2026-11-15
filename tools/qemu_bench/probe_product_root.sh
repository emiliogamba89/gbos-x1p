#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
DUMP=$(ls "$HERE"/../../downloads/tools/*/bin/dump.erofs | head -n1)
RAW=/home/zero89/disk-run.raw
"$DUMP" --offset=6034554880 --path=/ "$RAW" 2>&1 | head -6
echo ====
"$DUMP" --offset=6034554880 --path=/product/etc "$RAW" 2>&1 | head -5
