# Fase 2 — Banco QEMU ARM64 (approccio gbos-vm)

> Obiettivo: avviare il **kernel mica reale** in `qemu-system-aarch64` per
> confermare **F1 (EFI/DT boot chain)** e la pipeline di boot, prima di ogni
> tentativo bare-metal sul ThinkBook.
>
> Il recovery mica è già dimostrato funzionare in QEMU su Mac (gbos-vm):
> il kernel GKI parte con il **DT generato da QEMU** per la macchina `virt`,
> confermando che il kernel non richiede il DT Dell per decommitare.

## Payload (già costruito)

`tools/qemu_bench/build_payload.py` crea in `downloads/mica/payload/`:

| File | Contenuto |
|---|---|
| `kernel.bin` | kernel GKI mica **decompresso** (Image.lz4 → Image ARM64, 42,5 MiB, magic valido) |
| `initrd.img` | GKI ramdisk (init_boot, 2,7 MiB) + vendor ramdisk (29,7 MiB, 2 frammenti cpio lz4, 146 moduli) concatenati |
| `cmdline_q1.txt` | cmdline minimale con `console=ttyAMA0` (serial QEMU virt) |
| `cmdline_mica.txt` | cmdline originale mica (console=null) |

## Installazione QEMU sul ThinkBook (Windows ARM64)

**Via consigliata: WSL2 (ARM64 nativo, TCG veloce quanto serve)** — richiede
prompt **amministratore**:

```bat
winget install --id Microsoft.WSL -e
wsl --install -d Ubuntu-24.04
:: riavvia se richiesto, poi dentro Ubuntu:
sudo apt update && sudo apt install -y qemu-system-arm
```

Poi dal prompt Ubuntu:

```bash
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
bash run_qemu.sh q1
```

**Alternativa (sconsigliata)**: QEMU x86_64 via `winget install qemu` → doppia
emulazione (x64 emulato su WoA che emula aarch64): boot in ore, solo come ultima
spiaggia.

## Milestone

| ID | Test | Criterio di successo |
|---|---|---|
| **Q1** | kernel + initrd + cmdline Q1 (`console=ttyAMA0`) | log kernel su serial: versione, CPU, memoria, decompressione initramfs, `Run /init` |
| **Q2** | come Q1, si osserva l'init Android | messaggi di init (anche errori di partizioni/SELinux: normali in QEMU virt) |
| **Q3** | disco recovery attaccato (`-drive` con recovery.bin, virtio) + vendor rebuild Cuttlefish (porting gbos-vm) | boot fino al desktop (lontano, dipende dal porting vendor) |

## Note tecniche

- `-machine virt` fornisce il **DTB generato da QEMU**: è l'equivalente del DT
  che il firmware ABL fornisce sul Googlebook (la Fase 1 ha dimostrato che il
  DT non è sul disco).
- Il kernel è `Image.lz4` (CONFIG_KERNEL_LZ4): decompresso da
  `build_payload.py` perché `-kernel` di QEMU con Image raw è la via più diretta.
- cmdline Q1: `console=ttyAMA0` (PL011 di virt), `root=/dev/ram0 init=/init`.
- TCG su 8 core: il boot fino a `/init` richiede minuti, non secondi.
- Uscita da QEMU `-nographic`: `Ctrl-A` poi `X`.
