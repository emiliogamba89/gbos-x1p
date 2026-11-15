#!/usr/bin/env python3
"""Controlla fonts_customization.xml in product_a (disk-run.raw)."""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extend_system_lp import lp_extents

RAW = Path("/home/zero89/disk-run.raw")
BIN = next(Path(__file__).resolve().parent.glob("../../downloads/tools/*/bin"))
dump = str(BIN / "dump.erofs")
ext = lp_extents(RAW, "product_a")
print("extent product_a:", ext)
r = subprocess.run([dump, f"--offset={ext[0][0]}",
                    "--path=/product/etc/fonts_customization.xml",
                    "--cat", str(RAW)], capture_output=True)
data = r.stdout
print("byte:", len(data), "stderr:", r.stderr.decode(errors="replace")[:200])
out = Path("/home/zero89/fonts_customization.xml")
out.write_bytes(data)
hits = re.findall(rb'Noto[^<"]*CJK[^<"]*', data)
print("riferimenti CJK:", len(hits), hits[:6])
print("famiglie:", len(re.findall(rb"<family", data)))
