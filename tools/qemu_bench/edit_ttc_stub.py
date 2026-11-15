#!/usr/bin/env python3
"""system_port.py: stub CJK -> TTC validi a 4 subface (od-verified anchors)."""
import struct
from pathlib import Path

SRC = Path(__file__).resolve().parent / "system_port.py"
lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

# 1) riga del font clock: nome var estratto dal testo stesso
ci = next(i for i, l in enumerate(lines) if "AndroidClock.ttf" in l and "run(" in l)
CLK = lines[ci].split(" = run(")[0].split()[-1]
assert len(CLK) > 5 and CLK.endswith("s"), repr(CLK)
print("CLK:", repr(CLK))

# 2) nomi stub dal loop cjk
sline = next(l for l in lines if "for cjk in (" in l)
sans = sline.split('("')[1].split('"')[0]
serif = sline.split('", "')[1].split('"')[0]
print("stub:", repr(sans), repr(serif))

BUILD = (
    "    # TTC minimalista: la config font cita gli stub con index>0 (i .ttc\n"
    "    # originali hanno piu' subface per peso/lingua) e la copia in\n"
    "    # /data/fonts/config sopravvive tra i boot: un TTF a faccia singola\n"
    "    # fa lanciare IllegalArgumentException -> FontManagerService_create\n"
    "    # muore senza complete() -> onBootPhase resta in join() -> boot fermo.\n"
    "    # ttcf con 4 offset tutti validi: qualunque index risolve (tofu CJK).\n"
    "    _sfnt_off = 12 + 16\n"
    "    cjk_bytes = (b\"ttcf\" + struct.pack(\">II\", 0x00010000, 4)\n"
    "                 + struct.pack(\">4I\", *([_sfnt_off] * 4)) + " + CLK + ")\n"
    "    assert struct.unpack_from(\">4I\", cjk_bytes, 12) == (_sfnt_off,) * 4\n"
    "    assert cjk_bytes[_sfnt_off:_sfnt_off + 4] == " + CLK + "[:4]\n"
)
VERIFY = (
    "    assert cat(\"/system/fonts/" + sans + "\") == cjk_bytes, \"stub CJK non combacia\"\n"
    "    assert cat(\"/system/fonts/" + serif + "\") == cjk_bytes, \"stub CJK non combacia\"\n"
)

# self-check del TTC costruito dal codice inserito
fake = b"\x00\x01\x00\x00" + bytes(256)
ns = {CLK: fake, "struct": struct}
exec("if True:\n" + BUILD, ns)
cjk = ns["cjk_bytes"]
assert cjk[:4] == b"ttcf" and len(cjk) == 28 + len(fake)
assert struct.unpack_from(">4I", cjk, 12) == (28, 28, 28, 28)
assert cjk[28:32] == fake[:4]
print("self-check TTC ok:", len(cjk), "byte simulati")

n0 = sum(l.count("cjk_bytes") for l in lines)
assert n0 == 0, "cjk_bytes gia' presente?"

# 3) addfile nel loop CJK (indent 12, con il var clock dentro BytesIO)
ai = [i for i, l in enumerate(lines)
      if l.startswith(" " * 12) and ".addfile(ti," in l and CLK in l and "BytesIO(" in l]
assert len(ai) == 1, ai
lines[ai[0]] = lines[ai[0]].replace(CLK, "cjk_bytes")

# 4) BUILD subito dopo la riga clock
lines.insert(ci + 1, BUILD)

# 5) VERIFY dopo l'assert emoji
ei = next(i for i, l in enumerate(lines)
          if "assert cat(" in l and "NotoColorEmoji.ttf" in l and CLK in l)
lines.insert(ei + 1, VERIFY)

n1 = sum(l.count("cjk_bytes") for l in lines)
assert n1 == 3 + 1 + 2, n1
text = "".join(lines)
SRC.write_text(text, encoding="utf-8")
compile(text, str(SRC), "exec")
print("edit OK + sintassi verificata")
