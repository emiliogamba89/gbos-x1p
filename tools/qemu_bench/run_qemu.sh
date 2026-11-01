#!/usr/bin/env bash
# Fase 2 / banco QEMU — avvia il kernel mica in qemu-system-aarch64.
#
# Uso (dentro WSL2 Ubuntu ARM64 o Linux ARM64):
#   WAIT_SECONDS=240 bash run_qemu.sh [q1|q2|v3]
#
# q1 = payload originale, cmdline minimale (boot chain test)
# q2 = payload con override cpio (test lista moduli)
# v3 = stile gbos-vm: initrd blob unico (platform+init, niente frammento
#      recovery), cmdline androidboot.*, disco recovery su virtio-blk RO,
#      GICv3, USB xhci
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD="$HERE/../../downloads/mica/payload"
V4="$HERE/../../downloads/mica/v4"
RECOVERY="$HERE/../../downloads/mica/android-desktop_signed_recovery_image.bin"
LOG="$HERE/qemu-serial.log"
MODE="${1:-q1}"
WAIT="${WAIT_SECONDS:-300}"

CMDLINE=$(cat "$PAYLOAD/cmdline_${MODE}.txt")
INITRD="$PAYLOAD/initrd.img"
KERNEL="$PAYLOAD/kernel.bin"
MACHINE="virt,virtualization=on,gic-version=2"
EXTRA=()

case "$MODE" in
  q2) INITRD="$PAYLOAD/initrd_q2.img" ;;
  v3) INITRD="$PAYLOAD/initrd_v3.img"
      KERNEL="$V4/kernel.Image"
      MACHINE="virt,gic-version=3,highmem=on,highmem-ecam=off"
      EXTRA=(-drive "if=none,media=disk,id=driveimage,format=raw,readonly=on,file=$RECOVERY"
             -device virtio-blk-pci,drive=driveimage
             -device qemu-xhci,id=xhci
             -device usb-kbd,bus=xhci.0
             -device usb-mouse,bus=xhci.0
             -audio none -nic none) ;;
esac

echo "[*] cmdline ($MODE): $CMDLINE"
echo "[*] log seriale: $LOG (attendo max ${WAIT}s)"
rm -f "$LOG"

qemu-system-aarch64 \
  -machine "$MACHINE" \
  -cpu cortex-a76 \
  -m 4G -smp 4 \
  -no-reboot \
  -kernel "$KERNEL" \
  -initrd "$INITRD" \
  -append "$CMDLINE" \
  -display none -serial "file:$LOG" \
  "${EXTRA[@]}" &
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
