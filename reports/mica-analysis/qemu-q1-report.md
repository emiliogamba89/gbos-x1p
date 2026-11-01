# QEMU bench — Report Milestone Q1 (2026-11-01)

**Esito: SUPERATO.** Il kernel Googlebook mica boota su hardware virtuale
generico ARM (`qemu-system-aarch64 -machine virt`, DT generato da QEMU,
nessuna tabella/partizione Dell).

## Log chiave (risalvato in `tools/qemu_bench/qemu-serial.log`, non committato)

- Kernel: `Linux version 6.12.81-android16-6-g08dd7534bf44-ab16287118-4k`
  (GKI, kleaf/clang 19, build 2026-09-08)
- `Machine model: linux,dummy-virt` → usa il **DT di QEMU**: conferma che il
  kernel accetta un device tree fornito dall'esterno (Fase 1, fork F2)
- `Trying to unpack rootfs image as initramfs...` → `Freeing initrd memory:
  31684K` → il nostro initrd (GKI ramdisk + vendor ramdisk concatenati) è
  accettato dal kernel
- `Run /init as init process` → **`init: init first stage started!`** → l'init
  Android del recovery parte
- Moduli caricati: `qti-regmap-debugfs`, `icc-clk`, `clk-qcom`, poi prova
  `camcc-x1e80100.ko`
- pKVM: `Protected hVHE mode initialized successfully` (il kernel ha il
  supporto protected KVM attivo da cmdline built-in)

## Scoperte

1. **CONFIG_CMDLINE built-in del GKI mica** (prepend automatico, ripristina il
   pezzo mancante del cmdline decodificato in Fase 1):
   `console=ttynull stack_depot_disable=on cgroup_disable=pressure
   kasan.stacktrace=off kvm-arm.mode=protected bootconfig`
2. **Console silenziosa voluta**: a metà boot l'init ri-silenzia la console
   (`printk: legacy console [ttynull0] enabled`): coerente col `console=null`
   del cmdline di produzione.
3. **Reboot loop**: senza il disco recovery, dopo il caricamento dei primi
   moduli il guest chiama `reboot('bootloader')` (comportamento normale del
   recovery che non trova il suo disco) → con `-no-reboot` QEMU si ferma invece
   di loopare (fix in `run_qemu.sh`).

## Conseguenze

- Fork **F1/F2**: il path **DT-based senza EFI** funziona (il kernel parte con
  solo DT + cmdline). Resta da verificare il path EFI/GRUB per il bare-metal.
- Fork **F3**: confermato di nuovo (moduli Qualcomm del vendor ramdisk si
  caricano su kernel GKI generico).
- Il prossimo obiettivo (Q2/Q3) è controllare l'userspace: **cpio override**
  (append di un cpio plain che sovrascrive file nel ramdisk: ultimo membro
  vince) per mantenere la console e diagnosticare il reboot, poi attacco del
  disco recovery via virtio (percorso gbos-vm).
