#!/usr/bin/env python3
"""FASE 0 (live USB Linux ARM64) - Raccolta inventario hardware del ThinkBook 16 QOY.

Eseguire DENTRO la live (Ubuntu Concept / Fedora aarch64), da terminale:
    sudo python3 tools/collect_hw_live.py

Output: reports/thinkbook-hardware/live/*.txt
Scrive solo nella cartella del progetto (montata in lettura/scrittura) o in /tmp.
"""
import os
import subprocess
import sys
from datetime import datetime


def find_outdir():
    """Preferisce reports/ dentro una cartella gbos-x1p montata, altrimenti /tmp."""
    candidates = []
    for base in ("/media", "/run/media/" + os.environ.get("USER", "user"), "/mnt"):
        if os.path.isdir(base):
            for root, dirs, _ in os.walk(base):
                if "gbos-x1p" in dirs or os.path.basename(root) == "gbos-x1p":
                    candidates.append(os.path.join(root, "gbos-x1p"
                                                   if "gbos-x1p" in dirs else ""))
                if len(candidates) > 3:
                    break
    for c in candidates:
        out = os.path.join(c, "reports", "thinkbook-hardware", "live")
        try:
            os.makedirs(out, exist_ok=True)
            probe = os.path.join(out, ".w")
            open(probe, "w").close()
            os.remove(probe)
            return out
        except OSError:
            continue
    out = "/tmp/gbos-x1p/reports/thinkbook-hardware/live"
    os.makedirs(out, exist_ok=True)
    return out


OUT = None


def run(name, cmd, must=False):
    print(f"[*] {name} ...")
    path = os.path.join(OUT, name)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# cmd: {' '.join(cmd)}\n# rc: {r.returncode}\n\n")
            f.write(r.stdout or "")
            if r.stderr:
                f.write("\n# --- stderr ---\n" + r.stderr)
        print(f"    ok -> {path}")
        return r.returncode
    except FileNotFoundError:
        print(f"    comando non trovato: {cmd[0]} (salto)")
        return 127
    except Exception as e:
        print(f"    ERRORE: {e}")
        return 1
    finally:
        if must:
            pass


def main():
    global OUT
    OUT = find_outdir()
    if os.geteuid() != 0:
        print("[!] ATTENZIONE: alcuni comandi (dmesg completo, dmidecode, acpidump) "
              "richiedono root. Meglio: sudo python3 " + sys.argv[0])

    with open(os.path.join(OUT, "_info.txt"), "w", encoding="utf-8") as f:
        f.write(f"Raccolta hardware live - {datetime.now().isoformat()}\n")
        f.write("Modello atteso: Lenovo ThinkBook 16 QOY, Snapdragon X Plus X1P-42-100\n")

    # Identita' sistema e boot
    run("uname.txt", ["uname", "-a"])
    run("cpuinfo.txt", ["cat", "/proc/cpuinfo"])
    run("efi.txt", ["sh", "-c", "ls -la /sys/firmware/efi || echo 'NON EFI?!'"])
    run("efibootmgr.txt", ["efibootmgr", "-v"])
    run("secureboot.txt", ["sh", "-c", "mokutil --sb-state 2>/dev/null || "
        "dmesg | grep -i -m5 'secure boot' || echo 'mokutil assente'"])

    # PCI + driver bindings (fondamentale: quali driver si legano a quali device)
    run("lspci-nn.txt", ["lspci", "-nn"])
    run("lspci-vv.txt", ["lspci", "-nn", "-vv"])
    run("lspci-k.txt", ["lspci", "-nn", "-k"])   # driver/kernel module in uso

    # USB
    run("lsusb.txt", ["lsusb"])
    run("lsusb-v.txt", ["lsusb", "-v"], )

    # DMI / ACPI / kernel
    run("dmidecode.txt", ["dmidecode"])
    run("acpidump.txt", ["sh", "-c", "acpidump > " + os.path.join(OUT, "acpidump.bin") + " 2>&1; ls -la " + os.path.join(OUT, "acpidump.bin")])
    run("dmesg.txt", ["dmesg"])
    run("proc-cmdline.txt", ["cat", "/proc/cmdline"])
    run("iomem.txt", ["cat", "/proc/iomem"])
    run("lsmod.txt", ["lsmod"])

    # Moduli Qualcomm/caricati con info (versione, firmware richiesti)
    run("modinfo-loaded.sh.txt", ["sh", "-c",
        "for m in $(lsmod | awk 'NR>1{print $1}' | grep -Ei 'qcom|ath11k|smmu|panel|drm|ec|hid' | head -40); "
        "do echo \"=== $m ===\"; modinfo $m 2>/dev/null | head -15; done"])

    # Storage e rete (inventario supporti e NIC)
    run("lsblk.txt", ["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL"])
    run("blkid.txt", ["blkid"])
    run("ip-addr.txt", ["ip", "-br", "addr"])
    run("rfkill.txt", ["rfkill", "list"])

    print("\n[OK] Fatto. Cartella output:", OUT)
    print("    Copia la cartella 'reports' su supporto esterno o caricala in rete.")


if __name__ == "__main__":
    sys.exit(main())
