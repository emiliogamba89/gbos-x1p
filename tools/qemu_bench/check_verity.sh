#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
{
echo "== verity su dm-0 (deve essere 0) =="
grep -ac "Built verity table: '1 /dev/block/dm-0" "$L"
echo "== mount system/vendor =="
grep -a "target=/system\|target=/vendor" "$L" | head -4
echo "== FEC corrections =="
grep -ac "corrected" "$L"
echo "== marker =="
grep -a "MARKER" "$L" | head -3
echo "== stop audioserver eseguiti =="
grep -a "stop audioserver" "$L" | head -4
echo "== audioserver SIGSEGV: $(grep -acE 'SIGSEGV.*audioserver|audioserver.*SIGSEGV' "$L")"
echo "== righe: $(wc -l < "$L")"
} 2>&1
