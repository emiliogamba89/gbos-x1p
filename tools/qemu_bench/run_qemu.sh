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
#      GICv3, USB xhci, GPU virtio (GPU=0 per ometterla)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PAYLOAD="$HERE/../../downloads/mica/payload"
V4="$HERE/../../downloads/mica-16471258/v4"
RECOVERY="$HERE/../../downloads/mica-16471258/android-desktop_signed_recovery_image.bin"
WRITABLE="$HERE/../../downloads/mica-16471258/disk-writable.raw"
LOG="$HOME/qemu-serial-live.log"  # fs nativo WSL: evita i problemi di cache drvfs
MODE="${1:-q1}"
WAIT="${WAIT_SECONDS:-300}"

CMDLINE=$(cat "$PAYLOAD/cmdline_${MODE}.txt")
INITRD="$PAYLOAD/initrd.img"
KERNEL="$PAYLOAD/kernel.bin"
MACHINE="virt,virtualization=on,gic-version=2"
EXTRA=()

case "$MODE" in
  q2) INITRD="$PAYLOAD/initrd_q2.img" ;;
  v3) INITRD="$PAYLOAD/initrd_v4.img"  # fstab splice; AVB/FEC is disabled by valid vbmeta flags=3, not by this alone.
      KERNEL="$V4/kernel.Image"
      MACHINE="virt,gic-version=3,highmem=on,highmem-ecam=off"
      if [ "${WRITABLE_DISK:-0}" = "1" ]; then
        # disco scrivibile; se WRITABLE_DISK_PATH punta a un file su fs NATIVO
        # (es. /home/...), usalo: drvfs (/mnt/c) rende le fsync di /data lentissime
        DISK="$WRITABLE"
        if [ -n "${WRITABLE_DISK_PATH:-}" ]; then
          if [ ! -f "$WRITABLE_DISK_PATH" ]; then
            echo "[*] copio il disco su fs nativo: $WRITABLE_DISK_PATH"
            cp --sparse=always "$WRITABLE" "$WRITABLE_DISK_PATH"
          fi
          DISK="$WRITABLE_DISK_PATH"
        fi
        EXTRA+=(-drive "if=none,media=disk,id=driveimage,format=raw,cache=unsafe,file=$DISK")
      else
        EXTRA+=(-drive "if=none,media=disk,id=driveimage,format=raw,readonly=on,file=$RECOVERY")
      fi
      EXTRA+=(-device virtio-gpu-gl-pci,xres=1080,yres=1920,max_outputs=1
             -device virtio-blk-pci,drive=driveimage
             -device qemu-xhci,id=xhci
             -device usb-kbd,bus=xhci.0
             -device usb-mouse,bus=xhci.0
             -audio none -nic none) ;;
esac

# Refuse before rotating the live log or trying to lock the writable disk.
if ps -eo args= | grep -Eq '(^|/)qemu-system-aarch64([[:space:]]|$)'; then
  echo '[!] QEMU aarch64 già attivo: fermarlo prima di avviare un altro boot.' >&2
  exit 1
fi

echo "[*] cmdline ($MODE): $CMDLINE"
echo "[*] log seriale: $LOG (attendo max ${WAIT}s)"
mv -f "$LOG" "$LOG.prev" 2>/dev/null || true  # MAI rm: se un QEMU vive, il log andrebbe nel file cancellato

LD_PRELOAD=/usr/lib/aarch64-linux-gnu/qemu/ui-opengl.so qemu-system-aarch64 \
  -machine "$MACHINE" \
  -cpu cortex-a76 \
  -m 4G -smp 6 \
  -no-reboot \
  -kernel "$KERNEL" \
  -initrd "$INITRD" \
  -append "$CMDLINE" \
  -display gtk,gl=on -serial "file:$LOG" \
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

# persistenza della seriale su /mnt/c a fine run
cp -f "$LOG" "$HERE/qemu-serial.log" 2>/dev/null || true
