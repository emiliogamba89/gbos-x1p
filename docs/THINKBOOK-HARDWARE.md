# ThinkBook 16 G7 QOY (21NH) — inventario hardware (Fase 0)

> Raccolto con `tools/collect_hw_windows.py` (dati completi in `reports/`,
> gitignored). Questo documento contiene solo IDs hardware: è il riferimento
> per il confronto con il recovery mica in Fase 1.

## Identità

| Campo | Valore |
|---|---|
| Modello | Lenovo ThinkBook 16 G7 QOY (21NH) |
| SoC | Snapdragon X Plus **X1P-42-100** (8× Oryon) |
| BIOS | LENOVO `PWCN37WW` (2025-11-24) |
| Piattaforma | **ACPI-first (WoA standard)**: DSDT + 8× PNP0A08 PCIe, MADT/GIC, GTDT, IORT, MCFG, PPTT, SPCR, DBG2, SDEV, TPM2 |

## PCI

| Dispositivo | ID | Note |
|---|---|---|
| Wi-Fi FastConnect 7800 (WCN7850) | `17CB:1107` SUBSYS `E0E917AA` | stesso chip di mica → ath11k |
| PCIe root port ×2 | `17CB:0111` | Qualcomm PCIe host |
| NVMe | `15B7:5016` (Samsung) | storage |

⚠️ La **GPU non è su PCI**: è un device **ACPI** (`VEN_QCOM&DEV_0D17`, Adreno X1-45).
Stesso schema atteso per la X1-85 di mica (`VEN_QCOM&DEV_0D16`?) — da verificare nel
DSDT del recovery per il confronto driver.

## Dispositivi ACPI chiave

| Funzione | HID | Note |
|---|---|---|
| **GPU** Adreno X1-45 | `VEN_QCOM&DEV_0D17` | SUBSYS `CRD08380` (= reference design Qualcomm) |
| NPU Hexagon | `QCOM0D0A` | ComputeAccelerator |
| **EC Lenovo (Fn keys)** | `IDEA200E` | driver Lenovo-specifico; confrontare con kernel mica |
| **Tastiera** (HID I2C) | `QTEC0001` | su bus I2C Qualcomm `QCOM0C10` |
| **Touchpad** (HID I2C) | `ELAN06FA` | stesso bus I2C |
| Bluetooth | `QCOM0C6B` (UART) + `QCOM0D04` (Aqstic ACX) | BT su **UART**, non USB |
| Audio DSP | `QCOM0C1B` + `QCOM0C82` | SoundWire/audio su DSP |
| USB xHCI host | `QCOM0D08`, `QCOM0D09`, `QCOM0CA1` | + dual-role Synopsys `QCOM0C8B/C` |
| SD/mmc | `QCOM2466` (BayHub) | lettore SD |
| IOMMU/SMMU | `QCOM068F` ×2, `VEN_QCOM&DEV_0C09` ×2 | critici per GPU/USB/Wi-Fi |
| USB-C UCSI | `USBC000` | PD/Type-C |
| Human Presence | `QCOM06D9` | sensore |
| Temperature/DCVS/policy | `QCOM0C5x`, `VEN_QCOM&DEV_0CFx` | gestione termica/power |

## Implicazioni per il progetto

1. **Console di debug**: `SPCR`+`DBG2` definiscono la porta console del firmware —
   utile per il boot probe (Fase 2) per catturare i log del kernel mica.
2. **Tastiera interna**: passa per `QTEC0001` (I2C) + `IDEA200E` (Fn). Il kernel mica
   avrà quasi certamente i driver Dell (non QTEC/IDEA): **tastiera interna probabilmente
   non funzionante** al primo boot → pianificare tastiera USB esterna (xHCI `QCOM0D08`
   dovrebbe invece funzionare, essendo SoC-standard).
3. **Touchpad**: `ELAN06FA` HID-over-I2C standard → buona probabilità che funzioni se
   il kernel mica ha il driver I2C Qualcomm (`qcom-geni-i2c`) e i2c-hid.
4. **Wi-Fi**: stesso WCN7850 di mica → drivers/firmware dell'immagine mica
   potrebbero funzionare as-is (board file `board-2.bin` da verificare).
5. **GPU**: `DEV_0D17` (X1-45) vs quella di mica: se i _HID differiscono, il kernel
   mica non binderà il device → possibile patch del DSDT del ThinkBook (difficile)
   o driver userspace alternativo (Mesa, come gbos-vm).
6. Piattaforma ACPI-first **confermata** → aumenta la probabilità che il kernel mica
   (stessa famiglia SoC, prodotto per il mercato PC) booti via **ACPI con EFI stub**:
   da verificare in Fase 1 con `unpack_bootimg`.
