#!/usr/bin/env python3
"""system_port.py: nel loop CJK anche ti.size deve usare len(cjk_bytes)."""
from pathlib import Path

SRC = Path(__file__).resolve().parent / "system_port.py"
lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

CLK = next(l for l in lines if "AndroidClock.ttf" in l and "run(" in l).split(" = run(")[0].split()[-1]
needle = "ti.size = len(" + CLK + ")"
cand = [i for i, l in enumerate(lines) if l.startswith(" " * 12) and needle in l]
assert len(cand) == 1, cand
print("riga:", cand[0], lines[cand[0]].rstrip())
lines[cand[0]] = lines[cand[0]].replace(needle, "ti.size = len(cjk_bytes)")

n = sum(l.count("cjk_bytes") for l in lines)
assert n == 7, n
SRC.write_text("".join(lines), encoding="utf-8")
compile("".join(lines), str(SRC), "exec")
print("edit OK:", n, "occorrenze cjk_bytes")
