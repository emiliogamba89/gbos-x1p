@echo off
cd /d C:\Users\emili\Desktop\gbos-x1p\tools\qemu_bench
wsl.exe -d Ubuntu-24.04 -- bash -c "cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench && WRITABLE_DISK=1 WAIT_SECONDS=5400 bash run_qemu.sh v3 > qemu_detached.out 2>&1"
