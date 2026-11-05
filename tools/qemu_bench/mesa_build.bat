@echo off
cd /d C:\Users\emili\Desktop\gbos-x1p\tools\qemu_bench
wsl.exe -d Ubuntu-24.04 -- bash -c "bash /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench/build_mesa_full.sh > /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench/mesa_build.out 2>&1"
