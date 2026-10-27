# Procedura acpidump su Windows (Fase 0)

> **Obiettivo**: ottenere le tabelle ACPI complete (e decompilate) del
> **ThinkBook 16 QOY**. Sono la materia prima della Fase 1: confronto con il
> kernel del recovery mica (ACPI vs DTB, EC, GPIO, I2C, dispositivi X1P).
>
> ⚠️ **Eseguire SOLO sul ThinkBook 16 QOY (il target).** I dump di altri PC
> non servono a nulla e vanno buttati.

## Modo automatico (consigliato)

Da un prompt di Windows **sul ThinkBook** (idealmente amministratore):

```bat
git clone https://github.com/emiliogamba89/gbos-x1p.git
cd gbos-x1p
python tools\collect_hw_windows.py
```

Lo script:
1. raccoglie IDs PCI/USB/ACPI, BIOS, GPU, `msinfo32`;
2. se manca `acpidump.exe`, scarica il package Chocolatey `iasl 2026.4.8`
   (che **incorpora** lo zip ufficiale Intel `iasl-win-20260408.zip`),
   verifica lo **SHA256 contro il valore pubblicato da Intel**
   (`121F5E4F30B1DF63D09052294E4A605D4DEE2DFB9599FA24AF4AC6015DF02B70`)
   e estrae `acpidump.exe`, `acpixtract.exe`, `iasl.exe` in `tools/bin/`
   (esclusi da git);
3. esegue la pipeline completa in `reports/thinkbook-hardware/windows/acpi/`:
   - `acpidump` → `acpidump.txt` (dump testuale completo, ~4 MB);
   - `acpixtract -a` → una `.dat` per tabella (DSDT, SSDT1..N, APIC, DMAR...);
   - `iasl -d` → le stesse in **ASL decompilato leggibile** (`.dsl`).

Opzione: `python tools\collect_hw_windows.py --acpi-only` per rieseguire solo
la parte ACPI.

Note:
- Su **Windows-on-ARM** i tool (x86_64) girano con l'emulazione integrata: ok.
- Se `acpidump` non produce output: riaprire il prompt **come amministratore**.
- Serve Python 3.8+ (solo stdlib). Nessun pacchetto da installare.

## Modo manuale

1. Scaricare i binari ufficiali ACPICA per Windows:
   <https://www.intel.com/content/www/us/en/download/774881/acpi-component-architecture-downloads-windows-binary-tools.html>
   (file `iasl-win-<versione>.zip`; verificare lo SHA256 mostrato nella pagina).
2. Estrarre `acpidump.exe`, `acpixtract.exe`, `iasl.exe` in `tools/bin/`.
3. Da prompt **amministratore**, nella cartella di output:
   ```bat
   acpidump > acpidump.txt
   acpixtract -a acpidump.txt
   iasl -d dsdt.dat ssdt1.dat ssdt2.dat ...
   ```

## Cosa cercare nei file (per la Fase 1)

Nei `.dsl` decompilati:
- `Device (EC*)`, `_HID` dell'Embedded Controller → confronto con i driver EC
  nel kernel mica (Dell) vs ThinkBook (Lenovo): il nodo chiave per la tastiera;
- `Device (PCI0)`, MCFG, `_CRS` → topologia PCIe (GPU Adreno, Wi-Fi WCN7850);
- `I2C*`, `SPI*`, `SNDW*` (SoundWire) → touchpad, audio, sensori;
- `GPIO` controller e loro `_AEI`/GpioIo → mapping pin board-specifici;
- `DBG2`/`SPCR` → porte di debug (utile se il kernel mica accetta console).
- Nota sulle tabelle: `DMAR` (Intel VT-d) e `NHLT` (audio Intel) presenti nel
  firmware sono normali anche su piattaforma Qualcomm; non implicano nulla.

## Privacy

I contenuti di `reports/` sono dati della macchina (IDs, software, seriale in
msinfo32): **non committarli** (già in `.gitignore`). Se servono alla community,
condividere solo gli estratti rilevanti (es. i soli `_HID` dell'EC).
