# GPOS-X1P — Googlebook OS (ARM64) su ThinkBook 16 QOY

> **Obiettivo**: avviare Googlebook OS ufficiale (recovery ARM64 "mica" per Dell XPS Googlebook,
> Snapdragon X Elite) su un **Lenovo ThinkBook 16 QOY con Snapdragon X Plus (X1P-42-100)**,
> replicando su ARM64 l'approccio del progetto **gbrunch** (preservare le partizioni Google
> originali e aggiungere un layer di compatibilità locale), adattandolo alla piattaforma
> Qualcomm X1 / Windows-on-ARM.

**Stato documento**: v1.0 — piano iniziale, nessuna fase ancora avviata.
**Riservatezza immagini**: il recovery Google non va mai ridistribuito; tutto viene
scaricato e costruito localmente (come richiedono anche gbrunch e gbos-vm).

---

## 1. Contesto e stato dell'arte

### 1.1 Cos'è Googlebook OS
- Nuovo OS desktop di Google: "ChromeOS ricostruito sullo stack Android" (**Android 17**).
- Nessuna ISO generica: solo **recovery per-device** nel catalogo ufficiale
  <https://dl.google.com/dl/edgedl/device/recovery/production_recovery.json>.
- 5 dispositivi al lancio: 3 x86_64 (Acer moonstone, ASUS lapis, Lenovo ruby) e
  2 ARM64 (Dell **mica**, HP quartz — entrambi Snapdragon X Elite).
- Il boot è Android standard: fastboot/fastbootd/recovery, partizioni A/B
  (`boot_a/b`, `vendor_boot_a/b`, `vbmeta_a/b`, `super`, `userdata`...), AVB.

### 1.2 Progetti di riferimento
| Progetto | Cosa fa | Rilevanza per noi |
|---|---|---|
| [danbyumagic/gbrunch](https://github.com/danbyumagic/gbrunch) | Googlebook OS x86 su laptop Intel UEFI: recovery ufficiale preservata + layer compat + GRUB → kernel Google originale. Testato su **1 solo** HP (Core Ultra 7 155U): desktop, grafica, Wi-Fi OK; webcam/audio NO. | **Modello architetturale** che vogliamo replicare su ARM64 |
| [skylartaylor/gbos-vm](https://github.com/skylartaylor/gbos-vm) | Recovery **mica** ARM64 in QEMU su Apple Silicon: vendor partition ricostruito con componenti virtuali Cuttlefish (KeyMint/Gatekeeper software, 3 regole SELinux grafiche, BT virtuale), GPU via Venus/MoltenVK. | Dimostra che il recovery mica parte **senza** hardware Dell se vendor/security vengono sostituiti. Fonte dei componenti software di sicurezza |
| [sebanc/brunch](https://github.com/sebanc/brunch) | Brunch framework per ChromeOS x86. | Precedente storico, architettura ROOTC (non direttamente riutilizzabile per Android) |

**Nessun progetto esistente punta a laptop Windows-on-ARM**: saremmo i primi
(aluminium-os.com lo dichiara esplicitamente). Ciò significa: aspettative realistiche,
approccio a fasi con criteri GO/NO-GO, e mai toccare il disco interno nelle prime fasi.

---

## 2. Hardware implicato

### 2.1 Target vs origine
| Componente | ThinkBook 16 QOY (target) | Dell XPS Googlebook "mica" (origine recovery) | Compatibilità attesa |
|---|---|---|---|
| SoC | **Snapdragon X Plus X1P-42-100** | Snapdragon X Elite X1E-80-100 | ✅ Stessa piattaforma Qualcomm X1; il mainline Linux supporta X1P42100 dal 6.16 |
| Board | Lenovo (WoA UEFI) | Famiglia reference **Bluey** (Qualcomm) | ⚠️ Le board differiscono, ma dal coreboot emerge che **Bluey è basata proprio su X1P-42-100**: il SoC del recovery è lo stesso del ThinkBook |
| GPU | Adreno X1-45 | Adreno X1-85 | ⚠️ Stessa famiglia driver (msm/freedreno), ma i blob userspace nel vendor mica sono tarati sull'X1-85 (firmware shader/ZAP per SKU): incognita maggiore |
| Wi-Fi/BT | FastConnect 7800 (WCN7850) | FastConnect 7800 (WCN7850) | ✅ Stesso chip; driver ath11k + firmware linux-firmware; possibile mismatch dei `board-2.bin` |
| Firmware boot | UEFI WoA (Insyde/Qualcomm), Secure Boot disattivabile | UEFI/ABL Googlebook | ✅ Il ThinkBook avvia kernel Linux ARM64 via EFI stub (Fedora aarch64 / Ubuntu Concept funzionano) |
| Input | Tastiera interna via EC Lenovo | Tastiera via EC Dell | ❌→⚠️ Il kernel mica avrà i driver Dell; l'EC Lenovo potrebbe non essere supportato → tastiera interna potrebbe non funzionare (fallback: tastiera USB) |
| Display | Pannello 16" Lenovo | Pannello 13.4" Dell OLED | ⚠️ Via ACPI dovrebbe funzionare con il driver DRM; backlight/DP-In da verificare |
| Audio | Codec Qualcomm SoundWire | Codec Qualcomm SoundWire | ⚠️ Probabilmente rotto inizialmente (come su gbrunch/HP) |
| Webcam | USB integrata | USB integrata | ⚠️ UVC standard: possibile che funzioni |

### 2.2 Perché è plausibile (i due indizi chiave)
1. **SoC identico**: Bluey (la famiglia board dei Googlebook Snapdragon) è definita in
   coreboot come `soc/qualcomm/x1p42100` = X1P-42-100 = il SoC del ThinkBook 16 QOY.
   Il kernel del recovery mica include quindi i driver per il nostro SoC.
2. **Catena di boot traducibile**: su x86 gbrunch fa `UEFI → GRUB → kernel Google (EFI stub)`.
   I kernel Android GKI hanno quasi sempre `CONFIG_EFI_STUB`, e i laptop X1 eseguono
   kernel Linux ARM64 dal UEFI (prova: Ubuntu Concept/Fedora). L'equivalente ARM è:
   `UEFI ThinkBook → GRUB aarch64-efi → kernel Google (EFI stub)`.

### 2.3 I fork decisionali critici (da chiudere in Fase 1)
| # | Domanda | Se SÌ | Se NO |
|---|---|---|---|
| F1 | Il kernel mica ha `CONFIG_EFI_STUB`? | Si può bootare dal UEFI del ThinkBook (come gbrunch) | Serve un bootloader Android-style (ABL/U-Boot) → complessità ×10 |
| F2 | Il kernel mica si configura via **ACPI** (stile WoA) o **device tree** (stile ChromeOS ARM)? | ACPI: il UEFI del ThinkBook fornisce le tabelle → fattibile | DTB: servirebbe un DT per il ThinkBook → quasi impraticabile (serve U-Boot + DT X1P custom) |
| F3 | Il kernel mica ha il supporto `CONFIG_ACPI` per X1 (quirk SMMU/ECAM come i patch WoA)? | Tutto procede | Test fermo finché non si capisce come il Googlebook espone l'hardware |

---

## 3. Architettura della soluzione

```
┌─────────────────────────────────────────────────────────────────┐
│ Recovery ufficiale mica (read-only, scaricata da Google)        │
│  boot_a/b · vendor_boot_a/b · vbmeta_a/b · super(system/...)    │
└──────────────────────────────┬──────────────────────────────────┘
                               │ import locale, hash verificati
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ Immagine compatibilità (costruita localmente)                   │
│  • ESP: GRUB aarch64-efi + kernel Google + initramfs compat     │
│  • boot/vendor_boot originali (kernel Google)                   │
│  • vbmeta re-firmato con --disable-verification                 │
│  • vendor ricostruito: KeyMint/Gatekeeper software (Cuttlefish, │
│    come gbos-vm), servizi hardware Dell mascherati, policy      │
│    SELinux patchate (solo scope grafico/buffer sharing)         │
│  • userdata Android fresca (non cifrata, sperimentale)          │
└──────────────┬──────────────────────────────┬───────────────────┘
               ▼                              ▼
     Trial su USB/SSD esterno       (poi, solo se tutto funziona)
     dal UEFI del ThinkBook         eventuale installazione interna
               ▼
   UEFI ThinkBook → GRUB aarch64 → kernel Google originale
               ▼
        Desktop Googlebook OS
```

Principi (ereditati da gbrunch):
1. Le partizioni di **sistema** Google restano byte-per-byte originali.
2. Vendor/SELinux/security sono **ricostruiti localmente** con componenti open
   (Cuttlefish/AOSP) — nessun file Google ridistribuito.
3. Si parte sempre da **USB esterno**; nessuna modifica al disco interno.
4. Ogni fase produce **log e report** prima di passare alla successiva.

---

## 4. Fasi del progetto

> Ogni fase ha: obiettivo, prerequisiti, attività, artefatti, **criteri GO/NO-GO**.
> Regola: si avanza solo con GO esplicito. Un NO-GO non è un fallimento: è un
> risultato di ricerca (a oggi nessuno ha dimostrato la fattibilità).

---

### FASE 0 — Preparazione e ricognizione hardware (1–2 giorni)

**Obiettivo**: ambiente di lavoro sicuro + inventario completo dell'hardware del ThinkBook.

**Prerequisiti**
- USB da ≥ 16 GB (Linux ARM64) + USB/SSD esterno da ≥ 64 GB (futuro trial, verrà cancellato).
- Backup completo di Windows/dati. Abilitare BitLocker **sospeso** solo se necessario; meglio avere i recovery key salvati.
- Secondo PC (questo) per download e build.

**Attività**
0. *(Da Windows, sul ThinkBook, zero rischi)* eseguire **sul ThinkBook 16 QOY** `python tools/collect_hw_windows.py` (vedi `docs/ACPIDUMP-WINDOWS.md`) → popola `reports/thinkbook-hardware/windows/` con IDs PCI/USB/ACPI, BIOS, msinfo32 **e dump ACPI completo decompilato** (DSDT/SSDT in ASL leggibile, con acpidump+acpixtract+iasl scaricati e verificati SHA256 automaticamente). Su Windows-on-ARM i tool x86 girano in emulazione. **Non eseguire su altri PC: i dump di macchine diverse dal target sono inutili.** I contenuti di `reports/` non vanno committati (già in `.gitignore`). **Nota**: questa parte NON sostituisce la live — il criterio GO (avvio kernel di terzi dal UEFI) si verifica SOLO con la USB.
1. Scaricare una distro Linux ARM64 per X1: **Ubuntu Concept** (x1e/x1p) o **Fedora Workstation aarch64**; scriverla in DD mode sulla USB.
2. Nel BIOS del ThinkBook: **Secure Boot OFF**, avvio UEFI USB.
3. Avviare Linux e verificare: boot UEFI ARM64 funziona; tastiera/touchpoint; quindi eseguire `python3 tools/collect_hw_live.py` (automatizza tutto). Riferimento manuale:
   ```bash
   sudo dmesg > dmesg-thinkbook.txt
   lspci -nn -vv > lspci.txt
   lsusb -v > lsusb.txt 2>/dev/null || lsusb > lsusb.txt
   sudo dmidecode > dmidecode.txt
   sudo acpidump > acpidump.bin   # da acpica-tools
   ls /sys/firmware/efi && efibootmgr -v
   cat /proc/cpuinfo; uname -a
   ```
4. Annotare gli ID esatti: GPU Adreno (PCI), Wi-Fi WCN7850 (PCI), EC/tastiera (ACPI HID), pannello, audio SoundWire.
5. Configurare SSH/rete per lavorare comodo dal ThinkBook avviato su Linux.

**Artefatti**: `reports/thinkbook-hardware/` (i file sopra + note).
**GO se**: il ThinkBook avvia Linux ARM64 da UEFI e il Wi-Fi funziona (prova che firmware/driver X1P girano). 
**NO-GO se**: il UEFI non avvia kernel di terzi anche con Secure Boot OFF (a quel punto il progetto bare-metal si ferma).

---

### FASE 1 — Acquisizione e analisi del recovery mica (2–4 giorni) ⚠️ *fase più critica*

**Obiettivo**: rispondere ai fork F1/F2/F3 (EFI stub? ACPI o DTB? supporto X1P?) **senza toccare il laptop**.

**Prerequisiti**: ~40 GB liberi su questo PC; WSL2/Linux con Python 3, `unzip`, `simget`.

**Attività**
1. **Download + verifica** (dati dal catalogo JSON, build corrente a ott. 2026):
   ```
   URL : https://dl.google.com/device/recovery/mica-user/16560795/recovery.zip
   MD5 : be97fb4fe368e50bb6102dcede1b2a80
   ZIP : ~7.1 GiB → immagine GPT 17.9 GiB
   Build: 16560795_CL3B.260622.276.R2 (branch arsp-26Q3-desktop-release)
   ```
   > Nota: il build citato in origine (17.CL3B.260622.273.R1 / 16471258) è stato sostituito
   > nel catalogo dalla .276.R2. Usare sempre l'MD5 del JSON corrente.
   → automatizzato da `python tools/fetch_mica.py` (catalogo, download, MD5 zip+bin,
   dump GPT, estrazione partizioni chiave). Solo stdlib, gira anche da Windows.
2. **Ispezione GPT**: `sgdisk -p` / `gdisk -l` sull'immagine; montare in loop read-only
   (`losetup -Pr --show -f`) oppure con `7z x` per le partizioni FAT/ext.
3. **Analisi kernel** (il cuore della fase):
   ```bash
   unpack_bootimg --boot_img boot_a.img --out out/boot_a/
   # → leggere: cmdline, DTB presente?, vendor_boot (vendor_cmdline, dtbo)
   strings out/boot_a/kernel | grep -i -E "efi|acpi"   # indizi rapidi
   # meglio: estrarre la config se inclusa (/proc/config.gz style o IKCONFIG)
   ```
   Verificare:
   - `CONFIG_EFI_STUB=y`? `CONFIG_ACPI=y`? quirks Qualcomm X1 (`CONFIG_QCOM_*`, SMMU v3 quirks)?
   - `cmdline` del boot: riferimenti a `androidboot.bootdevice`, `firmware_class.path`, `dtb=`, ecc.
   - Presenza di DTB in `vendor_boot`/`dtbo` (indizio: boot DT-based) o assenza + ACPI (indizio: boot WoA-style).
4. **Analisi vendor**: `lpunpack super.img` → `vendor.img`; `dump.erofs`/`fsck.erofs` (o ext4):
   - elenco HAL/servizi (hwservicemanager, keymint, gatekeeper, grafica: file blob Adreno `*X1*`/`a750`-like, firmware richiesti in `vendor/firmware`/`vendor/firmware_mnt`);
   - identificare i binari da sostituire con quelli software (KeyMint/Gatekeeper Cuttlefish, stile gbos-vm);
   - cercare componenti Dell-specifici (nomi "mica", DX13267, panel Dell, ecc.).
5. **Analisi moduli**: elenco `.ko` in vendor_boot/vendor → quali bus copre (PCIe, SoundWire, EC, ...). Cercare driver EC Dell vs assenza EC Lenovo.
6. Redigere il **report di fattibilità** con verdetto sui fork F1/F2/F3.

**Artefatti**: `reports/mica-analysis/` (layout GPT, config kernel, cmdline, inventario vendor, verdetto).
**GO se**: EFI stub + ACPI presenti e kernel con supporto X1 generico (caso ideale); oppure scenario DTB gestibile con U-Boot (→ ridefinire il piano con una Fase 2B U-Boot).
**NO-GO se**: kernel senza EFI stub **e** DTB bloccato alla board Dell → progetto sospeso (si resta in attesa che emergano analisi della community su mica/quartz).

---

### FASE 2 — Boot probe (1 settimana) — *il momento della verità*

**Obiettivo**: far stampare qualcosa al kernel Google sul ThinkBook, senza system/vendor completi.

**Approccio A (EFI stub, scenario favorevole)**
1. Immagine GPT su **SSD esterno via USB-C (consigliato: iterazioni più veloci, stesso flusso della Fase 3)** oppure USB stick ≥ 4 GB. Attenzione: il supporto verrà cancellato. Scrivere l'immagine in DD mode (Rufus-DD / `dd` / Etcher):
   - ESP FAT32 con GRUB nel **path removable** `\EFI\BOOT\BOOTAA64.EFI` (così parte dal menu F12 senza installare nulla nel NVRAM del ThinkBook);
   - kernel mica, initramfs BusyBox arm64 minimale (console + log su partizione + serial/EFIFB);
   - entry GRUB: `linux /Image console=ttyMSM0,115200 console=tty0 earlycon efi=debug ignore_loglevel loglevel=8 init=/bin/sh`.
2. Avvio dal menu F12 del ThinkBook, foto/video dello schermo, recupero log dalla USB.
3. Criterio: **il kernel decommita e arriva a `/bin/sh`** (anche senza display: aggiungere fallback USB serial? i laptop X1 non hanno UART facile → usare `printk` su schermo e netconsole se il Wi-Fi/Ethernet USB funzionasse nel kernel Google).

**Approccio B (solo DTB, scenario difficile)**: U-Boot aarch64 per QEMU come banco prova della catena, poi valutare U-Boot su ThinkBook — previo ridecisione del piano.

**Banco prova parallelo (consigliato, a basso rischio)**: replicare lo schema gbos-vm in
`qemu-system-aarch64 -M virt` su questo PC (TCG, lento ma ok per la pipeline):
verifica che la nostra immagine compatibilità (vendor ricostruito + vbmeta disabilitato)
partisca in un ambiente noto-prima del bare metal.

**Artefatti**: `probe/boot-probe.img`, `reports/boot-probe/` (foto, log).
**GO se**: il kernel mica esegue init su ThinkBook (anche con grafica assente).
**NO-GO parziale**: kernel decommita ma panic su SMMU/ACPI → iterare cmdline/quirk (tornare a Fase 1 per analisi), massimo 2–3 iterazioni prima di riconsiderare.

---

### FASE 3 — Trial completo su USB esterno (2–4 settimane)

**Obiettivo**: raggiungere il **desktop Googlebook OS** dal ThinkBook via USB/SSD esterno.

**Attività**
1. **Assemblaggio immagine** su USB/SSD esterno ≥ 64 GB (GPT, ~60+ GB):
   | Partizione | Contenuto | Origine |
   |---|---|---|
   | ESP | GRUB aarch64-efi, kernel, initramfs compat | locale |
   | boot_a/b, vendor_boot_a/b | originali mica | recovery (invariati) |
   | vbmeta_a/b | re-firmato `avbtool` con `--disable-verification` (per vendor modificato) | locale |
   | super | system/product/system_ext **originali**; **vendor ricostruito** | recovery + patch locali |
   | metadata, misc | create ex-novo | locale |
   | userdata | ext4/f2fs fresca, **non cifrata** | locale |
2. **Ricostruzione vendor** (chiave della fase), in stile gbos-vm:
   - KeyMint/Gatekeeper **software** (Cuttlefish) al posto di Trusty/secure element;
   - mascherare servizi HAL assenti/rotti (audio Dell, sensori, TCPC...);
   - 3 regole SELinux scoped per buffer sharing grafico (come gbos-vm), SELinux resta enforcing;
   - sostituire solo ciò che serve: ogni modifica documentata in `patches/vendor/CHANGELOG.md`.
3. **Primi boot** con `logcat`/`dmesg` persistenti su partizione log; iterare su:
   - seahorse/grafica (X1-45 vs blob X1-85: possibile primo muro);
   - Wi-Fi ath11k (firmware: provare quelli del vendor mica, poi linux-firmware);
   - input (tastiera USB esterna per i primi boot; EC Lenovo da investigare).
4. **Setup account**: usare SOLO un account Google di test (sicurezza software, dati non cifrati).

**Criteri di successo (gradini)**: kernel → init → surfaceflinger → launcher → Chrome renderizzato con GPU (anche sw-render prima) → Wi-Fi → accelerazione GPU reale.

**Artefatti**: `build/trial-usb.img` (script di build), `reports/trial/`, matrice hardware funzionante/rotta.

---

### FASE 4 — Iterazione hardware e consolidamento

- Grafica GPU accelerata (se i blob rifiutano X1-45: valutare Mesa freedreno userspace compilato per Android, come fa gbos-vm con Mesa/Venus);
- tastiera interna (EC Lenovo), touchpad, audio, Bluetooth, webcam, sospensione/ripresa;
- pulizia initramfs compat, riduzione hack, documentazione di TUTTO (l'obiettivo è un report utile alla community, alla stregue di `HP-RESULTS.md` di gbrunch);
- eventualmente proporre il progetto upstream a gbrunch/gbos-vm.

---

### FASE 5 — (Opzionale, SOLO dopo trial stabile) Installazione interna dual-boot

- Richiede ~60 GB non allocati, GPT/512B standard, Windows non cifrato o gestione BitLocker;
- l'installer non ridimensiona NTFS; piano di partizionamento revisionato e confermato con token;
- rollback documentato (rimozione voci EFI + ripristino GPT). 
- **Resta sconsigliata finché i gradini della Fase 3 non sono tutti verdi.**

---

## 5. Strumenti e prerequisiti riepilogo

| Dove | Strumenti |
|---|---|
| PC build (WSL2/Linux) | python3, unzip/xz, `sgdisk`, `losetup`, `unpack_bootimg`/`mkbootimg` (AOSP), `avbtool`, `lpunpack`/`lpmake`, `erofs-utils` (dump/fsck), `e2fsprogs`, `selinux` libsepol, `qemu-system-aarch64` + edk2-aarch64 (banco prova), `grub-mkstandalone` aarch64 |
| ThinkBook (Windows, Fase 0) | `tools/collect_hw_windows.py` — download+verifica automatici acpidump/acpixtract/iasl (vedi `docs/ACPIDUMP-WINDOWS.md`) |
| ThinkBook | USB Linux ARM64 (Ubuntu Concept o Fedora aarch64), USB/SSD esterno ≥ 64 GB |
| Download | recovery mica da `dl.google.com` (verifica MD5 del catalogo), componenti Cuttlefish da `ci.android.com` (per security software), Mesa/libsepol da upstream (come gbos-vm) |

## 6. Rischi e avvertenze

- ⚠️ **Perdita dati**: ogni scrittura su disco è potenzialmente distruttiva. Tutto su supporti esterni; mai `dd` verso il disco interno fino a Fase 5 (e lì solo con checklist).
- ⚠️ **Sicurezza**: installazione "unlocked/orange", chiavi in software, userdata non cifrata → account Google usa-e-getta, niente dati sensibili.
- ⚠️ **Nessun aggiornamento OTA**: installazione congelata alla build del recovery.
- ⚠️ **Nessuna garanzia**: crash, no-boot, hardware degradato in teoria possibile; il progetto è sperimentale al 100% (nessun precedente WoA).
- ⚖️ **Legale**: Googlebook OS è proprietario. Niente upload di recovery o immagini derivate; solo script e documentazione (stessa posizione di gbrunch/gbos-vm).

## 7. Registro di stato

| Fase | Stato | Esito |
|---|---|---|
| 0 — Ricognizione | 🟢 parte Windows completata (vedi `docs/THINKBOOK-HARDWARE.md`); manca la live USB (criterio GO) | ACPI-first confermata |
| 1 — Analisi mica | 🟡 strumento pronto (`fetch_mica.py`); download + analisi da eseguire | — |
| 2 — Boot probe | 🚫 bloccata da F1 | — |
| 3 — Trial USB | 🚫 | — |
| 4 — Iterazione | 🚫 | — |
| 5 — Interno | 🚫 (sconsigliata) | — |

## 8. Prossimi passi immediati

1. ~~Preparare `tools/fetch_mica.py`~~ ✅ **pronto e testato**: `python tools/fetch_mica.py` (catalogo → download con MD5 → estrazione immagine → dump GPT in `reports/mica-analysis/gpt.txt` → estrazione `boot/vendor_boot/vbmeta` in `downloads/mica/extract/`). ~30 GB liberi richiesti.
2. Preparare `tools/analyze_recovery.sh` (unpack boot/vendor_boot, config kernel, inventario vendor) → produce il report della Fase 1.
3. In parallelo (Fase 0): creare la USB Ubuntu Concept/Fedora ARM64 e raccogliere `reports/thinkbook-hardware/`.
