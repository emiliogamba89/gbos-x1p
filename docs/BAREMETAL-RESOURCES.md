# Risorse bare-metal ThinkBook 16 G7 QOY (Fase 5)

Raccoglie i riferimenti esterni validati, con cosa danno al progetto.

## 1. DT upstream per il ThinkBook 16 G7 QOY (Jens Glathe)

- Series: `tb16-dt` — `x1p42100-lenovo-thinkbook-16.dts` (v12, ago 2025, + patch HDMI dic 2025)
- https://patchew.org/linux/20250810-tb16-dt-v10-0-0bfed6d75c69@oldschoolsolutions.biz/
- Riferimenti: lkml 2025/5/15/1921 (v1), lkml.iu.edu 2508.2/09537 (v12), spinics msg5975087 (HDMI)

**Dà al progetto**: il device tree completo upstream per ESATTAMENTE questo
portatile (X1P-42-100 / x1p42100). Funzioni supportate dal DT: USB-C/A,
keyboard, touchpad, touchscreen, display + PWM backlight, PCIe, NVMe, SDHC,
ath12k WCN7850 Wi-Fi/BT (17CB:1107 confermato), ADSP/CDSP, GPIO keys, audio,
DP/HDMI. Include anche una patch a `drivers/firmware/qcom/qcom_scm.c` (1 riga
per la compatibilità X1P). Questo è il DT di riferimento per il boot bare-metal;
il kernel mica (6.12.81-android16) va verificato contro questo DTS.

## 2. dtbloader (TravMurav)

- https://github.com/TravMurav/dtbloader
- **Lenovo ThinkBook 16 G7 QOY è nella lista dei dispositivi supportati**
  (DMI-matched, con fixup device-specific).

**Dà al progetto**: il modo supportato per bootare OS DT-based su questa
macchina: driver EFI che installa il DTB nella config table UEFI (con fixups).
Da installare su ESP come driver (`DriverOrder` via efibootmgr/bcfg) o in
`/EFI/systemd/drivers/`. Cerca i DTB in `/dtbloader/dtbs/`, `dtbs/`, `/` dell'ESP.
Compatibile con il boot DT-based del kernel mica (3 overlay hamoa CRD).
ATTENZIONE (loro warning): non toccare mai le partizioni bootloader del device.

## 3. Fedora Snapdragon WoA install (beta 45)

- https://fedoraproject.org/wiki/Snapdragon_WoA_Laptop_Install_(Fedora_Beta)

**Dà al progetto** (kernel cmdline + workaround per bare-metal):
- `clk_ignore_unused` — obbligatorio su X1E/X1P: il kernel spegne i clock non
  ancora claimati e il boot muore prima del caricamento driver
- `systemd.tpm2_wait=0` — evita 90 s di timeout systemd TPM2 (TPM2 efivar
  presente ma nessun /dev/tpmrm0 senza driver)
- `scmi-cpufreq` come modulo forzato (`/etc/modules-load.d/`) — autoload SCMI rotto
- `qcom-firmware-extract` (dnf) — estrae firmware GPU/DSP model-specific dalla
  partizione Windows; utile anche per Fase 0 (collettore hw) e per il bare-metal
- Schermo nero ~30 s durante il boot: atteso

## 4. Linux-on-Snapdragon (Jeremiah-Hawley)

- https://github.com/Jeremiah-Hawley/Linux-on-Snapdragon
- Note pratiche: Ubuntu Concept / ALARM / Gentoo su X Elite; repo include
  firmware per Lenovo; `qcom-firmware-extract` da Ubuntu live; repartizione SSD
  con Bitlocker da disattivare prima.

**Dà al progetto**: percorso di riferimento per un live ARM64 USB (Fase 0),
estrazione firmware e template di partizionamento — da tenere come fallback se
il percorso Fedora incontra problemi.

## Impatto sul piano

- Fase 0 (collettore hw): `qcom-firmware-extract` aggiungibile a
  `tools/collect_hw_live.py` come fonte firmware.
- Fase 5 (bare-metal): GRUB/EFI con dtbloader + DTB da `x1p42100-lenovo-thinkbook-16.dts`
  compilato per il kernel scelto + cmdline `clk_ignore_unused systemd.tpm2_wait=0`.
  Verificare `CONFIG_ACPI` del kernel mica resta irrilevante se si va su DT puro.
