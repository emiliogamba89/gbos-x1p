#!/usr/bin/env python3
"""Patch chirurgica di services.jar per il boot TCG mica/VM:
mAllowRestart = true -> false nel costruttore di com.android.server.Watchdog.
Con allowRestart=false il Watchdog registra i thread bloccati (log completo)
ma NON uccide system_server (ramo "Restart not allowed: *not* killing").
Sotto TCG il readPackageLPw (verifica X509 di ~600 firme) tiene main occupato
per minuti: il Watchdog 60s uccide a ciclo continuo (e' un kill-loop, non
una diagnosi). In un emulatore preferiamo il ritardo al riavvio infinito.
Uso: patch_watchdog.py <services.jar-in> <services.jar-out>
"""
import struct, sys, zipfile, io, shutil

def u2(b, o): return struct.unpack_from("<H", b, o)[0]
def u4(b, o): return struct.unpack_from("<I", b, o)[0]

def parse_dex(d):
    """restituisce dict con le tabelle indispensabili"""
    assert d[:4] == b"dex\n", "non e' un dex"
    string_ids_size, string_ids_off = u4(d, 56), u4(d, 60)
    type_ids_size, type_ids_off = u4(d, 64), u4(d, 68)
    field_ids_size, field_ids_off = u4(d, 80), u4(d, 84)
    method_ids_size, method_ids_off = u4(d, 88), u4(d, 92)
    class_defs_size, class_defs_off = u4(d, 96), u4(d, 100)

    bb = d
    def get_string(idx):
        off = u4(bb, string_ids_off + idx * 4)
        # uleb128 lunghezza in utf16 code units, poi dati MUTF-8
        p = off
        size = 0
        shift = 0
        while True:
            byte = bb[p]; p += 1
            size |= (byte & 0x7F) << shift
            if not (byte & 0x80): break
            shift += 7
        end = d.index(b"\x00", p)
        return d[p:end].decode("utf-8", errors="replace")

    def get_type(idx):
        return get_string(u4(bb, type_ids_off + idx * 4))

    def get_field(idx):
        e = field_ids_off + idx * 8
        class_idx, type_idx, name_idx = u2(bb, e), u2(bb, e + 2), u4(bb, e + 4)
        return get_type(class_idx), get_type(type_idx), get_string(name_idx)

    return {
        "d": d, "sis": string_ids_size, "sio": string_ids_off,
        "tis": type_ids_size, "tio": type_ids_off,
        "fis": field_ids_size, "fio": field_ids_off,
        "mis": method_ids_size, "mio": method_ids_off,
        "cis": class_defs_size, "cio": class_defs_off,
        "get_string": get_string, "get_type": get_type, "get_field": get_field,
    }

def uleb128(d, p):
    v = 0; shift = 0
    while True:
        b = d[p]; p += 1
        v |= (b & 0x7F) << shift
        if not (b & 0x80): return v, p
        shift += 7

def find_class_method_code(d, class_desc, method_name):
    """trova il code_item di un direct method e restituisce (code_off, insns_off, insns_size)"""
    cis, cio = d["cis"], d["cio"]
    for i in range(cis):
        e = cio + i * 32
        type_idx = u4(d["d"], e)
        if d["get_type"](type_idx) != class_desc:
            continue
        # class_data_off @ e+24 (interfaces 8, static fields 12, instance fields 16, direct 20, virtual 24)
        cdo = u4(d["d"], e + 24)
        dd = d["d"]
        p = cdo
        static_fields_n, p = uleb128(dd, p)
        instance_fields_n, p = uleb128(dd, p)
        direct_methods_n, p = uleb128(dd, p)
        virtual_methods_n, p = uleb128(dd, p)
        idx = 0
        for _ in range(static_fields_n):
            diff, p = uleb128(dd, p); idx += diff
            _, p = uleb128(dd, p)  # access flags
        idx = 0
        for _ in range(instance_fields_n):
            diff, p = uleb128(dd, p); idx += diff
            _, p = uleb128(dd, p)
        midx = 0
        for _ in range(direct_methods_n):
            mdiff, p = uleb128(dd, p); midx += mdiff
            access, p = uleb128(dd, p)
            coff, p = uleb128(dd, p)
            e = d["mio"] + midx * 8
            proto_idx = u2(d["d"], e + 2)
            name = d["get_string"](u4(dd, e + 4))
            if name == method_name and coff:
                # code_item: registers(2) ins(2) outs(2) tries(2) debug(4) insns_size(4) insns...
                insns_size = u4(d["d"], coff + 12)
                return coff + 16, insns_size  # offset dell'array insns
        break
    raise SystemExit(f"metodo {class_desc}->{method_name} non trovato")

def find_field_idx(d, class_desc, field_name):
    fis, fio = d["fis"], d["fio"]
    for i in range(fis):
        e = fio + i * 8
        c_idx, t_idx, n_idx = u2(d["d"], e), u2(d["d"], e + 2), u4(d["d"], e + 4)
        if d["get_string"](n_idx) == field_name and d["get_type"](c_idx) == class_desc:
            return i
    raise SystemExit(f"campo {class_desc}.{field_name} non trovato")

def main(src, dst):
    zin = zipfile.ZipFile(src)
    out_bytes = {}
    patched = False
    for n in zin.namelist():
        b = bytearray(zin.read(n))
        if n.endswith(".dex") and not patched:
            d = parse_dex(bytearray(b))
            cls = "Lcom/android/server/Watchdog;"
            try:
                fidx = find_field_idx(d, cls, "mAllowRestart")
            except SystemExit:
                continue  # la classe non e' in questo dex
            insns_off, insns_size = find_class_method_code(d, cls, "<init>")
            insns = bytearray(b[insns_off:insns_off + insns_size * 2])
            # trova iput-boolean vA, vB, field@mAllowRestart, poi indietro fino
            # alla const/4 vA, 1 piu' vicina con lo stesso registro A
            hits = []
            for p in range(0, len(insns) - 4, 2):
                op = insns[p]
                if op == 0x5C:  # iput-boolean vA, vB, field@CCCC
                    A = insns[p + 1] & 0xF
                    f = insns[p + 2] | (insns[p + 3] << 8)
                    if f != fidx:
                        continue
                    # scan indietro (max 80 unit) per const/4 vA, 1
                    for q in range(p - 2, max(0, p - 160), -2):
                        opq = insns[q]
                        if opq == 0x12:  # const/4
                            Bq, Aq = insns[q + 1] >> 4, insns[q + 1] & 0xF
                            if Aq == A:
                                if Bq == 1:
                                    hits.append((q, p, A))
                                break  # ultima riscrittura di vA prima dell'iput
                    break  # il costruttore inizializza mAllowRestart una sola volta
            if not hits:
                raise SystemExit("pattern const/4 1 + iput-boolean mAllowRestart non trovato")
            if len(hits) != 1:
                print(f"ATTENZIONE: {len(hits)} occorrenze, uso la prima")
            p, q, A = hits[0]
            print(f"patch @ insns+{p}: const/4 v{A}, 1 -> 0 (iput mAllowRestart @ +{q})")
            insns[p + 1] = (insns[p + 1] & 0xF) | (0 << 4)  # B=0
            b[insns_off:insns_off + insns_size * 2] = insns
            # aggiorna header dex: adler32 @8 + sha1 @12 (art altrimenti userebbe
            # la cache odrefresh compilata col vecchio checksum e la patch
            # sarebbe ignorata)
            import zlib, hashlib
            rest = bytes(b[12:])
            struct.pack_into("<I", b, 8, zlib.adler32(rest) & 0xFFFFFFFF)
            b[12:32] = hashlib.sha1(rest).digest()
            patched = True
        out_bytes[n] = b
    assert patched, "nessun dex patchato"
    # rezip con i CRC aggiornati
    zout = zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED)
    for n, b in out_bytes.items():
        zi = zipfile.ZipInfo(n, date_time=(2009, 1, 1, 0, 0, 0))
        zi.external_attr = 0o644 << 16
        zout.writestr(zi, b)
    zout.close()
    print("OK ->", dst)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
