#!/usr/bin/env python3
"""FASE 0 (parte Windows) - Raccolta inventario hardware del ThinkBook 16 QOY.

>>> DA ESEGUIRE SUL THINKBOOK 16 QOY (il target ARM), NON su altri PC! <<<
Su Windows-on-ARM i tool ACPICA (x86_64) girano tramite l'emulazione integrata.

Uso (prompt di Windows, idealmente come AMMINISTRATORE per acpidump):
    python tools/collect_hw_windows.py             # raccolta completa
    python tools/collect_hw_windows.py --acpi-only # solo parte ACPI

Cosa fa:
  1. Raccoglie IDs PCI/USB/ACPI, BIOS, video controller, report msinfo32.
  2. Se acpidump.exe (ACPICA) non e' presente:
     - scarica il package Chocolatey 'iasl' (che incorpora lo zip ufficiale Intel
       'iasl-win-20260408.zip' con acpidump/acpixtract/iasl),
     - verifica lo SHA256 contro il valore pubblicato da Intel,
     - estrae i tool in tools/bin/ (esclusi da git).
  3. Esegue acpidump + acpixtract + iasl -d: dump completo delle tabelle ACPI
     e decompilato leggibile di DSDT/SSDT (materia prima per la Fase 1).

Output: reports/thinkbook-hardware/windows/   (NON committare: dati della macchina)
Nota: NON sostituisce la live USB - il criterio GO (boot kernel di terzi)
si verifica solo avviando una distro ARM64 dalla USB.
"""
import hashlib
import io
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from urllib.request import urlopen

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "reports", "thinkbook-hardware", "windows")
ACPI_DIR = os.path.join(OUT, "acpi")
BIN_DIR = os.path.join(BASE, "tools", "bin")

ACPICA_VERSION = "20260408"
# SHA256 dello zip ufficiale Intel 'iasl-win-20260408.zip' (pagina Intel 774881)
ZIP_SHA256 = "121F5E4F30B1DF63D09052294E4A605D4DEE2DFB9599FA24AF4AC6015DF02B70"
# Mirror stabile: package Chocolatey che INCORPORA lo zip Intel (SHA256 verificato)
CHOCO_NUPKG_URL = "https://community.chocolatey.org/api/v2/package/iasl/2026.4.8"
INNER_ZIP = f"iasl-win-{ACPICA_VERSION}.zip"
NEEDED_EXES = ["acpidump.exe", "acpixtract.exe", "iasl.exe"]


def run(name, cmd, shell=False, cwd=None, timeout=300):
    print(f"[*] {name} ...")
    path = os.path.join(OUT, name)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, shell=shell,
                           cwd=cwd or OUT, timeout=timeout,
                           encoding="utf-8", errors="replace")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# cmd: {cmd}  (cwd: {cwd or OUT})\n# rc: {r.returncode}\n\n")
            f.write(r.stdout or "")
            if r.stderr:
                f.write("\n# --- stderr ---\n" + r.stderr)
        print(f"    ok (rc={r.returncode}) -> {path}")
        return r.returncode
    except Exception as e:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# cmd: {cmd}\n# ERROR: {e}\n")
        print(f"    ERRORE: {e}")
        return -1


def ps(name, script):
    run(name, ["powershell", "-NoProfile", "-Command", script])


def ensure_acpidump():
    """Trova acpidump.exe: PATH -> tools/bin -> download+verifica+estrazione."""
    w = __import__("shutil").which("acpidump")
    if w:
        print(f"[*] acpidump trovato nel PATH: {w}")
        return w
    exe = os.path.join(BIN_DIR, "acpidump.exe")
    if os.path.exists(exe):
        print(f"[*] acpidump gia' presente: {exe}")
        return exe

    print(f"[*] acpidump non trovato: scarico il package 'iasl' ({ACPICA_VERSION}) ...")
    print(f"    URL: {CHOCO_NUPKG_URL}")
    try:
        os.makedirs(BIN_DIR, exist_ok=True)
        nupkg_path = os.path.join(BIN_DIR, "iasl.nupkg")
        with urlopen(CHOCO_NUPKG_URL, timeout=120) as r, open(nupkg_path, "wb") as f:
            f.write(r.read())
        print(f"    scaricato: {nupkg_path} ({os.path.getsize(nupkg_path)} byte)")

        # Il nupkg e' uno zip che contiene lo zip Intel ufficiale
        with zipfile.ZipFile(nupkg_path) as nz:
            inner = nz.read(f"tools/{INNER_ZIP}")
        sha = hashlib.sha256(inner).hexdigest().upper()
        if sha != ZIP_SHA256:
            print(f"    SHA256 NON corrisponde! ({sha}) ANNULLATO.")
            print(f"    Atteso da Intel: {ZIP_SHA256}")
            return None
        print("    SHA256 verificato contro Intel: OK")

        with zipfile.ZipFile(io.BytesIO(inner)) as iz:
            for name in NEEDED_EXES:
                with open(os.path.join(BIN_DIR, name), "wb") as f:
                    f.write(iz.read(name))
        print(f"    estratti in {BIN_DIR}: {', '.join(NEEDED_EXES)}")
        return exe
    except Exception as e:
        print(f"    download fallito ({e}).")
        print("    Procedura manuale:")
        print("      1. scarica lo zip da https://www.intel.com/content/www/us/en/download/774881/")
        print(f"         (file {INNER_ZIP}, SHA256 atteso: {ZIP_SHA256})")
        print(f"      2. estrai acpidump.exe/acpixtract.exe/iasl.exe in {BIN_DIR}")
        print("      3. riesegui questo script")
        return None


def collect_acpi(acpidump_exe):
    """Dump completo tabelle ACPI + decompilato DSDT/SSDT leggibile."""
    os.makedirs(ACPI_DIR, exist_ok=True)
    print("[*] ACPI: dump completo delle tabelle (acpidump)...")
    # 1. dump testuale completo (su Windows meglio da prompt amministratore)
    r = subprocess.run([acpidump_exe], capture_output=True, text=True,
                       cwd=ACPI_DIR, timeout=300, encoding="utf-8", errors="replace")
    txt = os.path.join(ACPI_DIR, "acpidump.txt")
    with open(txt, "w", encoding="utf-8", errors="replace") as f:
        f.write(r.stdout or "")
        if r.stderr:
            f.write("\n# --- stderr ---\n" + r.stderr)
    if r.returncode != 0 or len(r.stdout or "") < 1000:
        print(f"    acpidump rc={r.returncode}. Riprovare da prompt AMMINISTRATORE:")
        print("      tasto destro su 'Terminale'/'Prompt comandi' -> Esegui come amministratore")
        print(f"    stderr: {(r.stderr or '').strip()[:300]}")
        return
    print(f"    ok: {txt} ({os.path.getsize(txt)} byte)")

    # 2. estrazione tabelle separate (.dat)
    r = subprocess.run([os.path.join(BIN_DIR, "acpixtract.exe"), "-a", "acpidump.txt"],
                       capture_output=True, text=True, cwd=ACPI_DIR, timeout=300,
                       encoding="utf-8", errors="replace")
    with open(os.path.join(OUT, "acpixtract.log"), "w", encoding="utf-8") as f:
        f.write(r.stdout or "")
        f.write(r.stderr or "")
    print(f"    acpixtract rc={r.returncode}")

    # 3. decompilazione leggibile DSDT/SSDT (il dato piu' prezioso)
    dats = [f for f in os.listdir(ACPI_DIR)
            if f.upper().startswith(("DSDT", "SSDT")) and f.lower().endswith(".dat")]
    if dats:
        r = subprocess.run([os.path.join(BIN_DIR, "iasl.exe"), "-d"] + dats,
                           capture_output=True, text=True, cwd=ACPI_DIR, timeout=600,
                           encoding="utf-8", errors="replace")
        with open(os.path.join(OUT, "iasl-decompile.log"), "w", encoding="utf-8") as f:
            f.write(r.stdout or "")
            f.write(r.stderr or "")
        dsl = [f for f in os.listdir(ACPI_DIR) if f.lower().endswith(".dsl")]
        print(f"    decompilate {len(dsl)} tabelle DSL: {', '.join(sorted(dsl)[:8])}...")
        print("    -> cerca in dsdt.dsl: EC, _HID, GPIO, I2C, SNDW, PCI0 (paragone con kernel mica)")
    else:
        print("    nessuna tabella .dat estratta da acpixtract (vedi acpixtract.log)")


def collect_pnp():
    """Inventario dispositivi via pnputil/PowerShell."""
    # IDs dispositivi PCI/USB connessi (il dato piu' importante)
    run("pnputil-devices.txt", "pnputil /enum-devices /connected", shell=True)

    # Elenco PnP leggibile: classe, nome, InstanceId (contiene VEN_/DEV_ o VID_/PID_)
    ps("pnp-present.csv",
       "Get-PnpDevice -PresentOnly | "
       "Select-Object Status,Class,FriendlyName,InstanceId | "
       "ConvertTo-Csv -NoTypeInformation")

    # Solo PCI: evidenzia GPU Adreno e Wi-Fi WCN7850
    ps("pci-devices.csv",
       "Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'PCI*'} | "
       "Select-Object Class,FriendlyName,InstanceId | ConvertTo-Csv -NoTypeInformation")

    # Solo USB (webcam, hub, BT radio...)
    ps("usb-devices.csv",
       "Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'USB*'} | "
       "Select-Object Class,FriendlyName,InstanceId | ConvertTo-Csv -NoTypeInformation")

    # Dispositivi ACPI (EC, tastiera, sensori: utile per il confronto col kernel mica)
    ps("acpi-devices.csv",
       "Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'ACPI*'} | "
       "Select-Object Class,FriendlyName,InstanceId | ConvertTo-Csv -NoTypeInformation")

    # BIOS / scheda madre / sistema
    ps("system-info.csv",
       "Get-CimInstance Win32_BIOS,Win32_BaseBoard,Win32_ComputerSystem,Win32_Processor | "
       "ConvertTo-Csv -NoTypeInformation")

    # GPU
    ps("video-controllers.txt",
       "Get-CimInstance Win32_VideoController | "
       "Select-Object Name,DriverVersion,PNPDeviceID,AdapterRAM | Format-List")


def main():
    acpi_only = "--acpi-only" in sys.argv
    if not acpi_only:
        print("[!] ricordati: questo script va eseguito SUL THINKBOOK 16 QOY (target ARM)")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "_info.txt"), "w", encoding="utf-8") as f:
        f.write(f"Raccolta hardware Windows - {datetime.now().isoformat()}\n")
        f.write("Modello atteso: Lenovo ThinkBook 16 QOY, Snapdragon X Plus X1P-42-100\n")
        f.write(f"acpidump: ACPICA {ACPICA_VERSION} (SHA256 zip verificato vs Intel)\n")

    if not acpi_only:
        collect_pnp()

        # Report completo msinfo32 (testo)
        msinfo = os.path.join(OUT, "msinfo32.txt")
        print("[*] msinfo32 (puo' metterci 1-2 minuti) ...")
        subprocess.run(["msinfo32", "/report", msinfo, "/categories", "+all"], timeout=300)

        acpidump_exe = ensure_acpidump()
    else:
        acpidump_exe = os.path.join(BIN_DIR, "acpidump.exe")
        if not os.path.exists(acpidump_exe):
            acpidump_exe = ensure_acpidump()

    if acpidump_exe:
        collect_acpi(acpidump_exe)

    print("\n[OK] Fatto. Cartella output:", OUT)
    print("    NON committare reports/ nel repo (dati specifici della macchina).")
    print("    Ricorda: il criterio GO della Fase 0 (boot kernel di terzi) richiede comunque la live USB ARM64.")


if __name__ == "__main__":
    sys.exit(main())
