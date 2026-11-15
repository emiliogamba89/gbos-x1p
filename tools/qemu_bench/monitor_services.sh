#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== i nostri servizi =="
grep -aiE "vendor.keymint-default|keymint|gatekeeper|boot-service.default|IBootControl" "$L" | grep -avE "avc:|QMI_FW" | head -20 | cut -c1-200
echo "== init: servizi non avviati / errori =="
grep -aiE "init:.*(could not|failed to start|not found.*service|Invalid keyword|Unable to)" "$L" | head -15 | cut -c1-200
echo "== servicemanager VINTF gatekeeper =="
grep -aiE "IGatekeeper" "$L" | head -5 | cut -c1-200
