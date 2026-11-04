#!/usr/bin/env python3
"""Trova gli xref alla stringa 'invalid checksum' di liblp nell'init del
recovery mica e disassembla la funzione incapsulante (per ricavare la formula
del checksum del formato LP nuovo, header 256 byte).

Uso (WSL): python3 disasm_liblp.py [percorso_init_bin]
"""
import re
import subprocess
import sys
from pathlib import Path

F = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ix/init_bin"
OB = "/home/zero89/clang-arm64/clang-r584948b/bin"

sections = subprocess.run([f"{OB}/llvm-readelf", "-S", F],
                          capture_output=True, text=True).stdout
needle = b"Logical partition metadata has invalid checksum."
data = Path(F).read_bytes()
target = data.find(needle)
print(f"stringa a file offset {hex(target)}")

va = None
secname = None
for line in sections.splitlines():
    m = re.match(r"\s*\[\s*\d+\]\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", line)
    if not m:
        continue
    try:
        addr, off, size = int(m.group(3), 16), int(m.group(4), 16), int(m.group(5), 16)
    except ValueError:
        continue
    if off <= target < off + size:
        va = addr + (target - off)
        secname = m.group(1)
        break
assert va is not None, "stringa non mappata in nessuna sezione"
print(f"sezione {secname}, VA = {hex(va)}")

dis = subprocess.run([f"{OB}/llvm-objdump", "-d", "--no-show-raw-insn", F],
                     capture_output=True, text=True).stdout
lines = dis.splitlines()
low = va & 0xFFF
hits = []
for i, l in enumerate(lines):
    m1 = re.search(r"adrp\s+(x\d+),\s+([0-9a-f]+)", l)
    if not m1:
        continue
    for j in range(i + 1, min(i + 10, len(lines))):
        m2 = re.search(r"add\s+(x\d+),\s+(x\d+),\s+#(0x[0-9a-f]+|\d+)", lines[j])
        if m2 and m2.group(1) == m1.group(1) and int(m2.group(3), 0) == low:
            hits.append((i, j, l.strip(), lines[j].strip()))
            break
print(f"{len(hits)} candidati adrp+add (low12 {hex(low)}):")
for i, j, l1, l2 in hits[:24]:
    print(f"  L{i}: {l1} | {l2}")

if hits:
    i0 = hits[0][0]
    lo = max(0, i0 - 120)
    hi = min(len(lines), i0 + 40)
    print("=== contesto disassembly ===")
    for l in lines[lo:hi]:
        print(l)
