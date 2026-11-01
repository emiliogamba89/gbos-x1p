#!/usr/bin/env bash
# Fase 2 / banco QEMU — avvia il kernel mica in qemu-system-aarch64 (Milestone Q1).
#
# Uso (dentro WSL2 Ubuntu ARM64 o Linux ARM64):
#   bash run_qemu.sh [q1|mica]
#
# q1  = cmdline minimale con console=ttyAMA0 (vediamo i log del kernel)   [default]
# mica = cmdline originale di mica (console=null: output solo nel log file)
#
# Esci da QEMU: Ctrl-A poi X
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD="$HERE/../../downloads/mica/payload"
LOG="$HERE/qemu-serial.log"
MODE="${1:-q1}"

[ -f "$PAYLOAD/kernel.bin" ] || { echo "payload mancante: lancia prima build_payload.py (su Windows)"; exit 1; }

CMDLINE=$(cat "$PAYLOAD/cmdline_${MODE}.txt")
INITRD="$PAYLOAD/initrd.img"
[ "$MODE" = "q2" ] && INITRD="$PAYLOAD/initrd_q2.img"
WAIT="${WAIT_SECONDS:-300}"

echo "[*] cmdline ($MODE): $CMDLINE"
echo "[*] log seriale: $LOG (attendo max ${WAIT}s)"
rm -f "$LOG"

qemu-system-aarch64 \
  -machine virt,virtualization=on,gic-version=2 \
  -cpu cortex-a76 \
  -m 4G -smp 4 \
  -no-reboot \
  -kernel "$PAYLOAD/kernel.bin" \
  -initrd "$INITRD" \
  -append "$CMDLINE" \
  -display none -serial "file:$LOG" &
QPID=$!

for i in $(seq 1 "$WAIT"); do
  sleep 1
  if grep -qs "reboot: Restarting" "$LOG"; then echo "[i] reboot rilevato"; break; fi
  if ! kill -0 "$QPID" 2>/dev/null; then echo "[i] qemu terminato"; break; fi
done
kill "$QPID" 2>/dev/null || true
wait "$QPID" 2>/dev/null || true

echo "=== ULTIME 50 RIGHE DEL LOG ==="
tail -50 "$LOG"
