#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== ctl.restart zygote =="
grep -a "ctl.restart" "$L" | grep -a zygote | tail -5 | cut -c1-200
echo "== richieste reboot / soft reboot / rescue =="
grep -aiE "Rebooting system|requesting reboot|soft reboot|RescueParty|crashrecovery|recovery.*(reboot|restart)|sys.powerctl" "$L" | grep -av QMI_FW | tail -10 | cut -c1-200
echo "== righe proprio prima del kill (1212.5-1213.5) =="
grep -aE "\[ *121[23]\." "$L" | grep -avE "QMI_FW|NMI backtrace|Hardware name|pstate|pc :|lr :|x[0-9]+ ?:" | head -20 | cut -c1-210
