#!/usr/bin/env bash
L=/home/zero89/qemu-serial-live.log
echo "== morte di system_server (untracked) =="
grep -aE "Untracked process.*system_server" "$L" | tail -8 | cut -c1-220
echo "== Fatal signal di system_server =="
grep -aE "Fatal signal.*(pid (1543|4504|7219|1442|1326)|\((system_server)\))" "$L" | tail -8 | cut -c1-200
echo "== FATAL EXCEPTION recenti =="
grep -an "FATAL EXCEPTION" "$L" | tail -5
echo "== os.Debug / art abort / CHECK failed =="
grep -aiE "CHECK failed|art::Runtime::Abort|Runtime aborting|abort message" "$L" | tail -8 | cut -c1-200
