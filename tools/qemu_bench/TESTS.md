# QEMU bench — matrice dei test (aggiornata al 2026-11-01)

Il payload `initrd_q2.img` = initrd originale + override cpio (ultimo membro
vince sui path). Si genera con `python tools/qemu_bench/build_override.py`
(attenzione: il file attualmente contiene la lista di test `[icc-clk.ko]`).

## Come lanciare un test (WSL2 Ubuntu)

```bash
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
WAIT_SECONDS=240 bash run_qemu.sh q1   # payload originale, cmdline Q1
WAIT_SECONDS=240 bash run_qemu.sh q2   # payload con override, cmdline Q2
bash run_qemu.sh q3                    # variante kvm-arm.mode=nvhe
```

Il log seriale finisce in `qemu-serial.log`; lo script si autotermina al primo
`reboot:` del guest o allo scadere di `WAIT_SECONDS`.

## Risultati

| Test | Payload | Esito |
|---|---|---|
| Q1 | originale | **OK**: kernel boota, init first stage parte, 5 moduli poi reboot 'bootloader' |
| Override 6 moduli | override `modules.load` ridotto | identico al Q1: **l'init non usa quel file** |
| Override vuoto | `modules.load` + `modules.load.recovery` vuoti | identico: confermato |
| kvm-arm.mode=nvhe | cmdline q3 | KVM in nVHE ma lista identica |
| Override `[icc-clk.ko]` | lista da 1 modulo | identico: confermato |

## Causa trovata (storia corretta)

1. Il vendor_boot contiene **2 frammenti taggati**: `platform` (kind=1) e
   `recovery` (kind=2, 60 MB). Il frammento recovery contiene
   `modules.load.recovery` (108 moduli Qualcomm): **l'init leggeva QUEL file**
   (recovery mode di default), per questo gli override su `modules.load` erano
   ignorati.
2. La **bootconfig** nascosta nel vendor_boot (`androidboot.hardware=android-desktop`,
   `androidboot.load_modules_parallel=true`) non veniva passata da QEMU.
3. Il super del recovery È popolato (vendor erofs @5647630336+1024,
   system_dlkm @8188329984+1024: il superblock EROFS sta a +1024, non
   allineato a 4096 - il primo check era un falso negativo).
4. **Config kernel estratta (IKCONFIG)**: `CONFIG_EFI_STUB=y` (F1 confermata),
   `CONFIG_VIRTIO_PCI=m`, `CONFIG_VIRTIO_BLK=m` (moduli da system_dlkm).

## Milestone v3 (stile gbos-vm)

`build_initrd_v3.py` ricompone l'initrd come blob gzip unico:
`platform cpio + init cpio + override` (frammento recovery SCARTATO);
cmdline con tutti gli `androidboot.*`; disco recovery su virtio-blk RO;
GICv3. Per il disco servono i moduli virtio firmati da system_dlkm:
`sudo apt install erofs-utils && bash extract_virtio.sh` (in WSL), poi
`python build_initrd_v3.py` (su Windows, incorpora i moduli) e `run_qemu.sh v3`.
