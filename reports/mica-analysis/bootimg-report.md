# Mica boot images analysis v2 - 2026-11-01T11:45:53.356955
# Solo metadati/valori chiave (nessun contenuto Google).

## vbmeta_a (descriptor AVB — dimensioni verificate)

## boot_a
- kernel_size (u32 @8): 20445831 (19.50 MiB)
- verifica aritmetica AVB: align(20445831,4096)+4096 = 20451328 (AVB0 trovato a 20451328 per ksize=20445831)
- kernel estratto: C:\Users\emili\Desktop\gbos-x1p\downloads\mica\extract\kernel_a.bin (20445831 byte)

## Config kernel (IKCONFIG embed)
- IKCONFIG NON presente

## DTB builtin nel kernel
- FDT a offset kernel 12047161, total_size 1677136696 byte
- stringhe FDT informative:
  - `microsoft,vmgenid`
  - `4?pmK`
  - `HID_ANY_ID`
  - `dHIDPP_FFJ`
  - `panel`
  - `et/phy/mdio-board`
  - `1hidrA!-c?G`
  - `90hidjA`
  - `hidp`
  - `0hid`
  - `Afhidg->`
  - `%shidraw`
  - `QCOM`
  - `,hide_`
  - `SAMSUNG`
  - `d HID++`
  - `1hid`
  - `hId)%s1`
  - `samsung,`
  - `5HID`
  - `V0hid3`
  - ` BuCL2Geni<`
  - `B'hid`
  - `ausbhid`
  - `qcombphyy`
  - `ENGENIO`
  - `ATMEL`
  - `P;Td HID{`
  - `x1ed;`
  - `/0hid`
  - `:RPmkfs.`
  - `3genirq: Fai`
  - `qcom,smem`
  - `AHID`
  - `3HIDm`
  - `Rhidpp`
  - `JSHID++`
  - `qSamsungt`
  - `%3hid`
  - `PANEL`

## vendor_boot_a (VNDRBOOT v4, page 2048)
- header_version=4 page=2048 ramdisk_addr=0x10008000 dtb_addr=0x11000000 vendor_ramdisk_size=29723681
- **cmdline**: `clk_ignore_unused pd_ignore_unused efi=noruntime efi=novamap android_arch_task_struct_size=512 id_aa64mmfr1.vh=0 arm64_sw.hvhe=0 irqaffinity=0-3 pcie_ports=compat cpufreq.default_governor=performance kvm-arm.ffa-unmap-on-lend=full,nr_handles=8192 kvm-arm.ffa_max_nr_constituents=16384 firmware_class.path=/vendor/firmware,/vendor/firmware_mnt/image console=null 8250.nr_uarts=4 console_msg_format=syslog log_buf_len=1M cgroup_disable=pressure root=/dev/ram0 reserve_mem=20M:2M:trace trace_instance=boot_mapped^traceoff@trace drm.trace=0x106 module_blacklist=cros_ec_debugfs proc_mem.force_override=ptrace binder.impl=rust no_console_suspend softlockup_panic=1 nmi_watchdog=panic pm.dpm_watchdog_enabled=1 cpufreq.default_governor=performance trace_instance=backup=boot_mapped cpuidle.governor=teo kvm-arm.protected_modules=qnoc-x1e80100.ko,pkvm-smc-filter.ko,rpmh-regulator.ko,clk-rpmh.ko,gcc-x1e80100.ko,gpucc-x1e80100.ko,pkvm-secure-memory-manager.ko,qcom_smmu_v2_v3_dispatcher.ko,pkvm_drng.ko bootconfig`
- FDT dopo il ramdisk: NO (DTB builtin nel kernel)
- chiavi androidboot presenti (4): androidboot.baseband, androidboot.hardware, androidboot.hardware.platform, androidboot.load_modules_parallel

## init_boot_a
- kernel_size=0 ramdisk_size=2724175 (GKI ramdisk)

## dtb_a / dtbo_a
- dtb_a: 2097152 byte, **tutta zero: True** → il DT base NON è sul disco: lo fornisce il firmware (ABL/QEMU)
- dtbo_a: magic d7b7ab1e (dtbo image OK=True), total=97858, entries=3, page=2048, ver=1
  - entry[0]: size=86981 rev=4294901760 id=0x00000000 fdt=False esempi: [',qcom,x1e80100@', 'hamoa-x1e80100-crd-.', 'Rpanel']
  - entry[1]: size=9899 rev=4294901760 id=0x00000000 fdt=False esempi: ['__overlay__0', 'qcom,wb-display7', 'Ypanel!']
  - entry[2]: size=850 rev=983041 id=0x00000000 fdt=False esempi: ['__overlay__0']

## vendor ramdisk (moduli .ko)
- cpio decompresso: 15.0 MiB, 108 moduli .ko
- moduli x1e80100 (8): lib/modules/camcc-x1e80100.ko, lib/modules/debugcc-x1e80100.ko, lib/modules/dispcc-x1e80100.ko, lib/modules/gcc-x1e80100.ko, lib/modules/gpucc-x1e80100.ko, lib/modules/pinctrl-x1e80100.ko, lib/modules/qnoc-x1e80100.ko, lib/modules/tcsrcc-x1e80100.ko
- **moduli x1p42100 (4)**: lib/modules/camcc-x1p42100.ko, lib/modules/gcc-x1p42100.ko, lib/modules/gpucc-x1p42100.ko, lib/modules/qnoc-x1p42100.ko
- nota: driver di livello superiore (ath11k, DRM, panel) non in questo ramdisk (nel vendor super o in stadi successivi) — inventario parziale

## Stringhe kernel indicative (occorrenze)
- `dell`: 2
- `x1e80100`: 1
- `x1e`: 3
- `x1p`: 6
- `acpi`: 12
- `qcom,geni`: 2

## Verdetto Fase 1
- F1 (EFI stub): **probabile Sì** — cmdline con efi=noruntime/novamap; piattaforma UEFI Qualcomm; da confermare in QEMU (approccio gbos-vm)
- F2 (ACPI vs DT): **DT-based** — dtbo con overlay CRD hamoa-x1e80100; dtb_a tutta zero; nessun FDT in vendor_boot/kernel → **il DT base lo genera il firmware** (Qualcomm ABL; in QEMU, QEMU stesso)
- F3 (X1P-42100): **Sì a livello SoC** — moduli gcc/gpucc/camcc/qnoc-x1p42100 nel vendor ramdisk (la famiglia Googlebook copre X Elite E X Plus)
- Impatto Fase 2 (ThinkBook): console=null da overridare; DTB da fornire via GRUB (comando devicetree, DT adattato da CRD hamoa x1e80100) O test ACPI puro (se il kernel GKI ha CONFIG_ACPI); tastiera USB esterna obbligatoria
