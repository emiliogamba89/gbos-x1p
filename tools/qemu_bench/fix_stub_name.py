#!/usr/bin/env python3
"""Normalizza il nome del set di stub (due righe con stesso nome)."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent / "system_port.py"
lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)
fixed = []
for i, ln in enumerate(lines, start=1):
    if re.match(r'\s*\w+\s*=\s*\{\s*\'NotoSansCJK', ln) and 'NotoSerif' in ln:
        ln = re.sub(r'\w+\s*=', "CJK_STUBS =", ln, count=1)
        fixed.append((i, "def", ln))
    elif "names &" in ln:
        ln = re.sub(r'names & \w+', "names & CJK_STUBS", ln, count=1)
        fixed.append((i, "use", ln))
for i, tag, ln in fixed:
    print(i, tag, ln.rstrip())
assert len(fixed) == 2, "attese 2 righe"
SRC.write_text("".join(lines), encoding="utf-8")
compile(SRC.read_text(encoding="utf-8"), str(SRC), "exec")
print("OK")
