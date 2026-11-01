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
echo "[*] cmdline ($MODE): $CMDLINE"
echo "[*] log seriale: $LOG  (Ctrl-A X per uscire)"

exec qemu-system-aarch64 \
  -machine virt,virtualization=on,gic-version=2 \
  -cpu cortex-a76 \
  -m 4G -smp 4 \
  -no-reboot \
  -kernel "$PAYLOAD/kernel.bin" \
  -initrd "$PAYLOAD/initrd.img" \
  -append "$CMDLINE" \
  -nographic 2>&1 | tee "$LOG"
