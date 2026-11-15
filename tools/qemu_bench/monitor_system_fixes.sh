#!/usr/bin/env bash
set -u
sleep "${1:-0}"
L=/home/zero89/qemu-serial-live.log
printf '\n== framework and boot ==\n'
grep -aE 'Entered the Android system server|SystemServer:|boot_completed|Boot is finished|BOOT_COMPLETED|BootAnimation|SurfaceFlinger.*(ready|Boot|boot)|Starting phase' "$L" | tail -35
printf '\n== fixes and parse failures ==\n'
grep -aE 'zz-vm-fixes|VM-SYSTEM|audioserver|updatable_crashing|Invalid keyword|Invalid command|Parse.*error|Unable to.*(parse|action)|unexported property' "$L" | tail -45
printf '\n== crashes/restarts ==\n'
grep -aE "zygote.*(exited|SIGKILL)|Fatal signal|FATAL EXCEPTION|Kernel panic|crash.*(4 times|5 times)|watchdog bite" "$L" | tail -20
printf '\n== ART verification ==\n'
grep -aE 'Bad checksum|Failure to verify dex|VerifyError|Verifier rejected|ClassNotFoundException.*SystemServer|Entered the Android system server|AndroidRuntime.*FATAL' "$L" | tail -15
printf '\n== latest ==\n'
tail -10 "$L"
