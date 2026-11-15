#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
DUMP=$(ls "$ROOT"/downloads/tools/*/bin/dump.erofs | head -n1)
IMG=$(ls "$HERE"/system-port/system.orig.erofs)
OUT=/home/zero89/fonts-check
mkdir -p "$OUT"
"$DUMP" --path=/system/etc/fonts.xml --cat "$IMG" > "$OUT/fonts.xml"
echo "== riferimenti ai file stub in fonts.xml:"
grep -n 'CJK\|ColorEmoji' "$OUT/fonts.xml" | head -40 || true
echo "== tot famiglie: $(grep -c '<family' "$OUT/fonts.xml")"
for p in /system/etc/fonts_customization.xml /system/etc/fallback-fonts.xml /system/etc/preinstalled-fonts.xml; do
  echo "== $p:"
  "$DUMP" --path="$p" "$IMG" 2>&1 | head -2 || true
done
