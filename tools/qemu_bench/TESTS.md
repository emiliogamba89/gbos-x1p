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
| Override `[icc-clk.ko]` | lista da 1 modulo | DA ESEGUIRE |

## Punto aperto (rimuovere il reboot 'bootloader')

La sequenza di caricamento moduli osservata è SEMPRE (fissa):
`pkvm_drng (blocklist) → qti-regmap-debugfs → icc-clk → clk-qcom → camcc-x1e80100`
dopo `camcc`: `DebugSymbol: cannot get compatible node` → ~1s → `reboot('bootloader')`.

Non dipende da: `modules.load` (sovrascritto senza effetto), `modules.load.recovery`,
`kvm-arm.mode`. Il binario `/init` non contiene liste hardcoded (verificato).
Ipotesi correnti: (a) l'init carica per **alias/MODALIAS uevent**, (b) legge il
file da un path visibile dopo lo switch `first_stage_ramdisk`, (c) l'ordine è
guidato da `modules.dep`+`modules.alias` indipendente da `modules.load`.

`DebugSymbol: cannot get compatible node` + reboot = il probe di `camcc-x1e80100`
fallisce su hardware assente (QEMU virt) e la policy Google Desktop reboota.
Questa è una **divergenza attesa su hardware virtuale**: il recovery reale gira
solo con il suo hardware; per QEMU servirà il vendor rebuild (Milestone Q3,
approccio gbos-vm) o un init/fstab modificato.
