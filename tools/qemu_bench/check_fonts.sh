#!/usr/bin/env bash
# Confronto byte-per-byte del font che fa fallire FontManagerService_create.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
DUMP=$(ls "$ROOT"/downloads/tools/*/bin/dump.erofs | head -n1)
ORIG=$(ls "$HERE"/system-port/system.orig.erofs)
NEW=$(ls "$HERE"/system-port/system.new.erofs)
WORK=/home/zero89/font-check
FONT=NotoSansCJK-Regular.ttc
echo "tool: $DUMP"
rm -rf "$WORK"; mkdir -p "$WORK/orig" "$WORK/new"
"$DUMP" --path="/system/fonts/$FONT" --cat "$ORIG" > "$WORK/orig/$FONT"
"$DUMP" --path="/system/fonts/$FONT" --cat "$NEW"  > "$WORK/new/$FONT"
os=$(stat -c %s "$WORK/orig/$FONT"); ns=$(stat -c %s "$WORK/new/$FONT")
oh=$(sha256sum "$WORK/orig/$FONT" | cut -c1-16); nh=$(sha256sum "$WORK/new/$FONT" | cut -c1-16)
hd=$(head -c4 "$WORK/new/$FONT" | od -An -tx1 | tr -d ' \n')
if cmp -s "$WORK/orig/$FONT" "$WORK/new/$FONT"; then verdict="IDENTICI"; else verdict="DIVERSI"; fi
echo "$FONT: orig=$os($oh) new=$ns($nh) header_new=$hd -> $verdict"
