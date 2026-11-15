#!/usr/bin/env bash
set -euo pipefail
# Linux truncates comm to 15 characters (qemu-system-aar); match argv instead.
mapfile -t pids < <(ps -eo pid=,args= | awk '$2 ~ /(^|\/)qemu-system-aarch64$/ {print $1}')
for p in "${pids[@]}"; do
  kill -TERM "$p"
  echo "TERM inviato a QEMU PID=$p"
done
for _ in {1..30}; do
  alive=0
  for p in "${pids[@]}"; do
    if kill -0 "$p" 2>/dev/null; then alive=1; fi
  done
  if [[ "$alive" = 0 ]]; then exit 0; fi
  sleep 1
done
echo 'QEMU ancora attivo: nessuna modifica disco consentita' >&2
exit 1
