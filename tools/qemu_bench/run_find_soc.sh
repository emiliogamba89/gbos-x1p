#!/usr/bin/env bash
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
python3 "$HERE/find_mica_soc.py" > /home/zero89/find_soc.out 2>&1
echo "exit=$?"
wc -c /home/zero89/find_soc.out
