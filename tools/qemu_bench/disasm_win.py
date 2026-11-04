#!/usr/bin/env python3
"""Disassembla una finestra intorno agli indirizzi dati (xref della stringa
'invalid checksum' di liblp nell'init mica). Uso: python3 disasm_win.py"""
import subprocess

F = "/tmp/ix/init_bin"
OB = "/home/zero89/clang-arm64/clang-r584948b/bin"
# finestra attorno al codice che carica la stringa 0x204148 (0x454460)
WINDOWS = [(0x454300, 0x454800)]
dis = subprocess.run([f"{OB}/llvm-objdump", "-d", "--no-show-raw-insn", F],
                     capture_output=True, text=True).stdout
for lo, hi in WINDOWS:
    print(f"=== {hex(lo)} .. {hex(hi)} ===")
    for l in dis.splitlines():
        m = l.split(":", 1)
        if len(m) != 2:
            continue
        try:
            a = int(m[0].strip(), 16)
        except ValueError:
            continue
        if lo <= a <= hi:
            print(l)
