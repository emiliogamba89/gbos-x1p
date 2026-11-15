#!/usr/bin/env python3
"""Patch v2 del Watchdog: oltre a mAllowRestart=false (v1), SOPPRIME il kill
in Watchdog.run() rimpiazzando con NOP le invoke-static di
  android.os.Process.killProcess(I)V
  java.lang.System.exit(I)V
In questa build ("WATCHDOG KILLING SYSTEM PROCESS" + GOODBYE + riavvio) il
kill non e' gated su mAllowRestart: senza questa patch ogni blocco >60s del
main thread sotto TCG uccide system_server.
Uso: patch_watchdog2.py <services.jar-in> <services.jar-out>
"""
import struct, sys, zipfile, zlib, hashlib

def u2(b, o): return struct.unpack_from("<H", b, o)[0]
def u4(b, o): return struct.unpack_from("<I", b, o)[0]

def parse_dex(d):
    string_ids_size, string_ids_off = u4(d, 56), u4(d, 60)
    type_ids_size, type_ids_off = u4(d, 64), u4(d, 68)
    proto_ids_size, proto_ids_off = u4(d, 72), u4(d, 76)
    field_ids_size, field_ids_off = u4(d, 80), u4(d, 84)
    method_ids_size, method_ids_off = u4(d, 88), u4(d, 92)
    class_defs_size, class_defs_off = u4(d, 96), u4(d, 100)

    def get_string(idx):
        off = u4(d, string_ids_off + idx * 4)
        p = off
        size = 0
        shift = 0
        while True:
            byte = d[p]; p += 1
            size |= (byte & 0x7F) << shift
            if not (byte & 0x80): break
            shift += 7
        end = d.index(b"\x00", p)
        return d[p:end].decode("utf-8", errors="replace")

    def get_type(idx):
        return get_string(u4(d, type_ids_off + idx * 4))

    def get_method(idx):
        e = method_ids_off + idx * 8
        return get_type(u2(d, e)), get_string(u4(d, e + 4))

    return {"d": d, "cis": class_defs_size, "cio": class_defs_off,
            "mis": method_ids_size, "mio": method_ids_off,
            "sis": string_ids_size, "sio": string_ids_off,
            "get_string": get_string, "get_type": get_type,
            "get_method": get_method}

def uleb128(d, p):
    v = 0; shift = 0
    while True:
        b = d[p]; p += 1
        v |= (b & 0x7F) << shift
        if not (b & 0x80): return v, p
        shift += 7

def methods_of(d, class_desc):
    """yields (method_name, code_off) per tutti i metodi (direct+virtual)"""
    if isinstance(class_desc, bytes):
        class_desc = class_desc.decode()
    dd = d["d"]
    for i in range(d["cis"]):
        e = d["cio"] + i * 32
        if d["get_type"](u4(dd, e)) != class_desc:
            continue
        cdo = u4(dd, e + 24)
        p = cdo
        sfn, p = uleb128(dd, p)
        ifn, p = uleb128(dd, p)
        dmn, p = uleb128(dd, p)
        vmn, p = uleb128(dd, p)
        for _ in range(sfn):
            _, p = uleb128(dd, p); _, p = uleb128(dd, p)
        for _ in range(ifn):
            _, p = uleb128(dd, p); _, p = uleb128(dd, p)
        for kind, cnt in ((0, dmn), (1, vmn)):
            midx = 0
            for _ in range(cnt):
                mdiff, p = uleb128(dd, p); midx += mdiff
                _, p = uleb128(dd, p)
                coff, p = uleb128(dd, p)
                if coff:
                    yield d["get_method"](midx)[1], coff
        return
    raise SystemExit(f"classe {class_desc} non trovata")

KILL_TARGETS = {(b"Landroid/os/Process;", "killProcess"),
                (b"Ljava/lang/System;", "exit"),
                (b"Ljava/lang/System;", "halt"),
                (b"Ljava/lang/Runtime;", "halt")}

def main(src, dst):
    zin = zipfile.ZipFile(src)
    out = {}
    done = False
    for n in zin.namelist():
        b = bytearray(zin.read(n))
        if n.endswith(".dex") and not done:
            d = parse_dex(bytearray(b))
            cls = b"Lcom/android/server/Watchdog;"
            try:
                runs = [(nm, c) for nm, c in methods_of(d, cls) if nm == "run"]
                assert runs, "Watchdog.run() non trovato"
            except SystemExit:
                continue
            coff = runs[0][1]
            insns_size = u4(b, coff + 12)
            insns_off = coff + 16
            insns = b[insns_off:insns_off + insns_size * 2]
            # mappa method_idx -> nop: invoke-static 0x71 (3 unit), range 0x77 (3)
            nopped = 0
            for p in range(0, len(insns) - 4, 2):
                op = insns[p]
                if op in (0x6e, 0x6f, 0x70, 0x71, 0x72):   # invoke-kind
                    midx = insns[p + 1] | (insns[p + 2] << 8)
                    # attenzione al byte alto di p+2 quando A e' grande: midx a 16 bit ok
                    try:
                        t, name = d["get_method"](midx)
                    except Exception:
                        continue
                    if (t.encode(errors="replace"), name) in KILL_TARGETS:
                        insns[p:p + 6] = b"\x00" * 6
                        nopped += 1
                        print(f"[nop] @{p} invoke {t.decode()}->{name}")
                elif op in (0x74, 0x75, 0x76, 0x77, 0x78):  # invoke-kind/range
                    midx = insns[p + 1] | (insns[p + 2] << 8)
                    try:
                        t, name = d["get_method"](midx)
                    except Exception:
                        continue
                    if (t.encode(errors="replace"), name) in KILL_TARGETS:
                        insns[p:p + 6] = b"\x00" * 6
                        nopped += 1
                        print(f"[nop] @{p} invoke/range {t.decode()}->{name}")
            assert nopped >= 2, f"attesi >=2 invoke da noppare, trovate {nopped}"
            b[insns_off:insns_off + insns_size * 2] = insns
            rest = bytes(b[12:])
            struct.pack_into("<I", b, 8, zlib.adler32(rest) & 0xFFFFFFFF)
            b[12:32] = hashlib.sha1(rest).digest()
            done = True
            print(f"[OK] Watchdog.run(): {nopped} invoke noppate")
        out[n] = b
    assert done, "nessun dex patchato"
    zout = zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED)
    for n, bb in out.items():
        zi = zipfile.ZipInfo(n, date_time=(2009, 1, 1, 0, 0, 0))
        zi.external_attr = 0o644 << 16
        zout.writestr(zi, bb)
    zout.close()
    print("OK ->", dst)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
