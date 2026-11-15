#!/usr/bin/env python3
"""Aggiunge a system_port.py la rimozione delle famiglie CJK stub da fonts.xml.
Token fragili (chiave xattr, classe TarInfo, nomi font) estratti dal file."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent / "system_port.py"
text = SRC.read_text(encoding="utf-8")

pax = re.search(r'"S[A-Z]+\.xattr\.security\.sel[A-Za-z]+"', text).group(0)
cls = re.search(r'(\w+)\.TarInfo\("system/etc/init/zz', text).group(1) + ".TarInfo"
m = re.search(r'for cjk in \("([^"]+)", "([^"]+)"\)', text)
sans, serif = m.group(1), m.group(2)
print("pax:", pax, "| cls:", cls, "| stubs:", sans, serif)

BUILD = '''    # fonts.xml: gli stub CJK sono TTF a faccia singola ma le famiglie li
    # citano con index>0 (i .ttc originali hanno piu' subface): Font.Builder
    # lancia IllegalArgumentException -> il task FontManagerService_create
    # muore SENZA complete() -> onBootPhase resta in mServiceStarted.join()
    # per sempre e il boot si blocca. Rimuoviamo le famiglie puntanti agli
    # stub: zero costo di spazio, nessun file nuovo da aggiungere.
    import xml.etree.ElementTree as ET
    fx_bytes = run([dump, "--offset=0", "--path=/system/etc/fonts.xml",
                    "--cat", str(orig)]).stdout
    fx_meta = meta("/system/etc/fonts.xml")
    STUBS = {@@SANS@@, @@SERIF@@}
    fx_root = ET.fromstring(fx_bytes)
    fx_gone = []
    for fam in list(fx_root):
        names = {el.text.strip() for el in fam.findall("font") if el.text}
        if names & STUBS:
            fx_gone.append(fam.get("name") or fam.get("lang") or "?")
            fx_root.remove(fam)
    assert fx_gone, "fonts.xml: famiglie CJK stub non trovate"
    fx_out = (b'<?xml version="1.0" encoding="utf-8"?>\\n'
              + ET.tostring(fx_root, encoding="utf-8"))
    print(f"[2d] fonts.xml: rimosse {len(fx_gone)} famiglie: {fx_gone}")
'''
BUILD = BUILD.replace("@@SANS@@", repr(sans)).replace("@@SERIF@@", repr(serif))

ENTRY = '''        ti = @@CLS@@("system/etc/fonts.xml")
        ti.size = len(fx_out)
        ti.mode = fx_meta[0] & 0o7777
        ti.uid, ti.gid, ti.mtime = fx_meta[1], fx_meta[2], EPOCH
        ti.pax_headers = {@@PAX@@: label}
        t.addfile(ti, io.BytesIO(fx_out))
'''
ENTRY = ENTRY.replace("@@CLS@@", cls).replace("@@PAX@@", pax)

VERIFY = '''    got_fx = cat("/system/etc/fonts.xml")
    assert (@@SANS@@.encode() not in got_fx
            and @@SERIF@@.encode() not in got_fx), \\
        "fonts.xml ancora con famiglie CJK stub"
'''
VERIFY = VERIFY.replace("@@SANS@@", repr(sans)).replace("@@SERIF@@", repr(serif))

pat1 = re.compile(r'\n([ \t]*print\("\[2c\][^\n]*\)\n)')
pat2 = re.compile(r'\n([ \t]*ti = \w+\.TarInfo\("system/etc/init/zz[^\n]*\)\n)')
pat3 = re.compile(r'\n([ \t]*assert [^\n]*NotoColorEmoji[^\n]*\n)')
for tag, pat in (("2c", pat1), ("zz", pat2), ("emoji", pat3)):
    assert len(pat.findall(text)) == 1, f"ancora {tag} non univoca"

text = pat1.sub(lambda mm: "\n" + mm.group(1) + BUILD, text)
text = pat2.sub(lambda mm: "\n" + ENTRY + mm.group(1), text)
text = pat3.sub(lambda mm: "\n" + mm.group(1) + VERIFY, text)
SRC.write_text(text, encoding="utf-8")
compile(text, str(SRC), "exec")
print("edit OK + sintassi verificata")
