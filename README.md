# GPOS-X1P — Googlebook OS (ARM64) su ThinkBook 16

Progetto sperimentale per avviare **Googlebook OS** ufficiale (recovery ARM64 del
Dell XPS Googlebook "mica", Snapdragon X Elite) su un **Lenovo ThinkBook 16 QOY con
Snapdragon X Plus (X1P-42-100)**, replicando su ARM64 l'approccio del progetto
[**gbrunch**](https://github.com/danbyumagic/gbrunch): le partizioni di sistema
Google restano intatte, tutto il resto (boot, vendor, sicurezza) è un layer di
compatibilità costruito localmente.

> ⚠️ **Sperimentale al 100%.** Nessuno ha ancora portato Googlebook OS su un laptop
> Windows-on-ARM: questo repo documenta un tentativo strutturato in fasi con criteri
> GO/NO-GO espliciti. Boot failure, crash, hardware non funzionante e perdita dati
> sono possibili. **Mai toccare il disco interno del laptop: tutto da USB esterno.**

---

## Cos'è Googlebook OS (e perché non è ChromeOS)

Googlebook OS è il nuovo OS desktop di Google: **ChromeOS ricostruito sullo stack
di Android** (build Android 17). Non esiste ISO generica: solo **recovery
per-device** nel
[catalogo ufficiale](https://dl.google.com/dl/edgedl/device/recovery/production_recovery.json).
Al lancio ci sono 5 dispositivi: 3 Intel (x86_64) e 2 Snapdragon X Elite (ARM64):

| Device | Codename | Produttore | Arch | Build corrente |
|---|---|---|---|---|
| Dell XPS Googlebook | **mica** | Dell | ARM64 | `16560795_CL3B.260622.276.R2` |
| HP Googlebook 14 | quartz | HP | ARM64 | `16560795_CL3B.260622.276.R2` |
| Acer/ASUS/Lenovo Googlebook | moonstone/lapis/ruby | — | x86_64 | `16658739_CL3B.260622.276.R4` |

Il boot è Android standard: partizioni A/B (`boot`, `vendor_boot`, `vbmeta`,
`super`), AVB, fastboot/recovery.

## Perché sul ThinkBook potrebbe funzionare

1. **Lo stesso SoC.** I Googlebook Snapdragon sono costruiti sulla famiglia di
   reference board Qualcomm **"Bluey"** — che dal codice coreboot risulta basata
   proprio su `x1p42100`, cioè lo **Snapdragon X Plus del ThinkBook 16 QOY**
   (mica usa l'X1E-80-100, stessa piattaforma X1, stessi driver).
2. **Catena di boot traducibile.** gbrunch su x86 fa `UEFI → GRUB → kernel Google
   (EFI stub)`. I kernel Android hanno EFI stub e i laptop X1 avviano kernel
   Linux ARM64 dal UEFI (Fedora aarch64 / Ubuntu Concept). L'equivalente ARM:
   `UEFI ThinkBook → GRUB aarch64 → kernel Google`.

Le incognite principali (verificate nella Fase 1): il kernel mica si configura via
**ACPI** (stile WoA) o via **device tree** (stile ChromeOS ARM)? I blob grafici
Adreno X1-85 accettano l'X1-45 del ThinkBook? La tastiera interna passa per un EC
Lenovo che il kernel Dell potrebbe non conoscere?

## Stato

| Fase | Descrizione | Stato |
|---|---|---|
| 0 | Ricognizione hardware (Windows script + live Linux ARM64) | 🟡 strumenti pronti |
| 1 | Download + analisi recovery mica (EFI stub? ACPI/DTB? X1P?) | 🟡 strumento pronto |
| 2 | Boot probe (GRUB aarch64 + kernel Google + initramfs log) | 🚫 bloccata da F1 |
| 3 | Trial completo su USB esterno (vendor rebuild, security software) | 🚫 |
| 4 | Iterazione hardware (GPU, tastiera, Wi-Fi, audio) | 🚫 |
| 5 | (Opzionale) installazione interna dual-boot | 🚫 sconsigliata |

Dettaglio completo con criteri GO/NO-GO: **[PLAN.md](PLAN.md)**.

## Struttura del repo

```
PLAN.md                    piano dettagliato delle fasi (il documento di riferimento)
docs/ACPIDUMP-WINDOWS.md   procedura acpidump su Windows (manuale e automatica)
tools/
  collect_hw_windows.py    Fase 0: inventario hardware da Windows (da eseguire SUL ThinkBook)
  collect_hw_live.py       Fase 0: inventario hardware da live Linux ARM64
  fetch_mica.py            Fase 1: download recovery mica + verifica MD5 + dump GPT
                           + estrazione partizioni chiave
reports/                   output locali (gitignored: dati della macchina)
downloads/                 recovery Google e derivati (gitignored: MAI committare)
```

## Uso rapido

**Fase 0 — su Windows, sul ThinkBook** (zero rischi, nessun prerequisito oltre Python):

```bat
python tools\collect_hw_windows.py
```

Raccoglie IDs PCI/USB/ACPI, msinfo32 e le **tabelle ACPI decompilate**
(acpidump/acpixtract/iasl scaricati automaticamente e verificati SHA256 contro Intel).

**Fase 1 — download e prima analisi del recovery** (~30 GB liberi):

```bat
python tools\fetch_mica.py            # catalogo → download → MD5 → dump GPT → estrazione
python tools\fetch_mica.py --list     # solo catalogo
```

## Avvertenze

- **Sicurezza**: qualsiasi installazione off l'AVB gira con chiavi software e dati
  non cifrati → usare **solo un account Google di test**, mai dati personali.
- **Nessun aggiornamento OTA**: l'installazione resta congelata alla build del recovery.
- **Privacy**: `reports/` e `downloads/` non vanno mai committati né condivisi
  interamente (già in `.gitignore`).

## Note legali

Googlebook OS è **software proprietario Google**. Questo repository **non contiene e
non conterrà** recovery image, kernel/ramdisk/vendor derivati da Google, né chiavi:
tutto viene scaricato da `dl.google.com` e costruito localmente con verifica degli
hash. Progetto indipendente, non affiliato a né approvato da Google, Lenovo, Dell,
HP o Qualcomm.

## Riferimenti

- [danbyumagic/gbrunch](https://github.com/danbyumagic/gbrunch) — l'architettura che
  ispira questo progetto, su x86 (testato su 1 laptop HP Intel)
- [skylartaylor/gbos-vm](https://github.com/skylartaylor/gbos-vm) — recovery **mica**
  ARM64 in QEMU su Apple Silicon; dimostra che il vendor/partizioni di sicurezza
  possono essere sostituiti con componenti software (Cuttlefish)
- [sebanc/brunch](https://github.com/sebanc/brunch) — il classico framework per
  ChromeOS su PC generici (x86)
- [Catalogo recovery ufficiale](https://dl.google.com/dl/edgedl/device/recovery/production_recovery.json)
