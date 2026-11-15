#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
FSCK=$(ls "$ROOT"/downloads/tools/*/bin/*ck.erofs | head -n1)
O=$(ls "$HERE"/system-port/system.o*.erofs)
N=$(ls "$HERE"/system-port/system.n*.erofs)
W=/home/zero89/font-diff
echo "fsck: $FSCK"
rm -rf "$W"; mkdir -p "$W/orig" "$W/new"
"$FSCK" --extract="$W/orig" --path=/system/fonts "$O"
"$FSCK" --extract="$W/new"  --path=/system/fonts "$N"
if diff -rq "$W/orig" "$W/new"; then
  echo "FONTS IDENTICI orig==new ($(ls "$W/orig" | wc -l) file)"
else
  echo "VEDI DIFF SOPRA"
fi
f="$W/new/NotoSansCJK-Regular.ttc"
ls -la "$f"
head -c4 "$f" | od -An -tx1
