#!/usr/bin/env python3
"""Estende la partizione GPT 'super' assorbendo le partizioni subito dopo di lei
e aggiunge una nuova extent LP a vendor_a nella zona assorbita (slot 0).

Il vendor ricostruito (SwiftShader ICD + ANGLE + minigbm) supera le extents LP
di vendor_a e i gap del super sono esauriti. Le partizioni assorbite sono
tutte gia' estratte nei payload locali e non servono piu' sul disco di banco:
- vbmeta_a/b: AVB spento (cmdline unlocked/orange); vbmeta originale resta nel
  recovery master e nel repo (estratto in downloads/mica/extract)
- init_boot_a/b: il ramdisk GKI viene passato da QEMU -initrd (initrd_v3.img)
- vendor_boot_a/b: estratti in downloads/mica-16471258/v4 (mica_v4.py)
Il disco e' una copia scrivibile di banco (disk-writable.raw): l'originale
non viene mai toccato.

Cosa tocca (tutto coerente):
  1. GPT primario+backup: super.last = last dell'ultima partizione assorbita,
     ricalcolo CRC32 array entry + CRC32 header
  2. LP metadata slot 0 (primario @super+12288):
     - block_device_size = nuova dimensione GPT del super (ricerca per valore)
     - nuova extent vendor_a [vecchia fine super .. nuova fine super)
     - ricalcolo sha256 tabelle + CRC32 header
  3. backup metadata e slot _b: stantii (liblp legge il primario; gia' stantii
     dalle espansioni precedenti, il boot funziona)
"""
import hashlib
import struct
import sys
import zlib
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
WRITABLE = BASE / "downloads" / "mica-16471258" / "disk-writable.raw"
SECT = 512
# catena di partizioni assorbibili consecutiva dopo il super (contenuti gia'
# estratti nei payload locali; slot B mai usati, slot A sostituiti da QEMU)
SWALLOW = ["vbmeta_a", "vbmeta_b", "init_boot_a", "init_boot_b",
           "vendor_boot_a", "vendor_boot_b"]


def crc(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def read_gpt(raw):
    with raw.open("r+b") as f:
        f.seek(512)
        h = bytearray(f.read(92))
        assert h[:8] == b"EFI PART", "header GPT"
        ent_lba, n, esz = struct.unpack_from("<QII", h, 72)
        f.seek(ent_lba * SECT)
        entries = bytearray(f.read(n * esz))
        disk_lba = raw.stat().st_size // SECT - 1
        f.seek(disk_lba * SECT)
        hb = bytearray(f.read(92))
        bent_lba, bn, besz = struct.unpack_from("<QII", hb, 72)
        f.seek(bent_lba * SECT)
        bent = bytearray(f.read(bn * besz))
    return h, entries, hb, bent


def find_entry(entries, esz, name):
    for i in range(len(entries) // esz):
        e = entries[i * esz:(i + 1) * esz]
        if e[56:128].decode("utf-16-le").split("\0")[0] == name:
            return i, struct.unpack_from("<QQ", e, 32)
    return None, None


def header_crc(h):
    h[16:20] = bytes(4)
    h[16:20] = struct.pack("<I", crc(bytes(h[:struct.unpack_from("<I", h, 12)[0]])))


def main():
    raw = WRITABLE
    h, entries, hb, bent = read_gpt(raw)
    esz = struct.unpack_from("<I", h, 84)[0]

    si, (s_first, s_last) = find_entry(entries, esz, "super")
    assert si is not None

    # verifica che la catena da assorbire sia consecutiva e adiacente al super
    chain = []
    for name in SWALLOW:
        i, fl = find_entry(entries, esz, name)
        assert i is not None, f"{name} non trovata"
        chain.append((i, fl))
    new_s_last = chain[-1][1][1]
    swallow_first = chain[0][1][0]
    expected = s_last + 1
    for name, (i, (first, last)) in zip(SWALLOW, chain):
        if s_last >= new_s_last:
            break  # GPT gia' esteso: la catena non e' piu' adiacente al super
        assert first == expected, f"{name}: non consecutiva ({first} != {expected})"
        expected = last + 1
    print(f"[GPT] assorbo {len(chain)} partizioni: super.last {s_last} -> {new_s_last}")
    if s_last >= new_s_last:
        print(f"[GPT] super gia' esteso a {s_last}, salto la parte GPT")
    else:
        gained = (new_s_last - s_last) * SECT
        print(f"[GPT] assorbo {len(chain)} partizioni: super.last {s_last} -> {new_s_last} "
              f"(+{gained >> 20} MiB)")

        # --- GPT: super.last in primario e backup + CRC ---
        for ents in (entries, bent):
            off = si * esz
            struct.pack_into("<Q", ents, off + 40, new_s_last)
        struct.pack_into("<I", h, 88, crc(bytes(entries)))
        struct.pack_into("<I", hb, 88, crc(bytes(bent)))
        header_crc(h)
        header_crc(hb)
        with raw.open("r+b") as f:
            f.seek(512)
            f.write(h)
            f.seek(struct.unpack_from("<Q", h, 72)[0] * SECT)
            f.write(entries)
            disk_lba = raw.stat().st_size // SECT - 1
            f.seek(disk_lba * SECT)
            f.write(hb)
            f.seek(struct.unpack_from("<Q", hb, 72)[0] * SECT)
            f.write(bent)
        print("[GPT] scritti header + entry (primario e backup)")

    # --- LP metadata slot 0 ---
    super_start = s_first * SECT
    with raw.open("r+b") as f:
        f.seek(super_start + 12288)
        m = bytearray(f.read(65536))
    hs = struct.unpack_from("<I", m, 8)[0]
    tsz = struct.unpack_from("<I", m, 44)[0]
    tables = bytes(m[hs:hs + tsz])
    ps, pc, psz = struct.unpack_from("<III", m, 80)
    es, ec, esz_l = struct.unpack_from("<III", m, 92)

    # il valore attuale nel header LP e' la dimensione ORIGINARIA del super
    # (prima dell'assorbimento: fino a swallow_first-1)
    orig_size = (swallow_first - s_first) * SECT
    new_size = (new_s_last - s_first + 1) * SECT
    # block_device_size nel layout AOSP sta @52 (dopo tables_hash): non e'
    # allineato a 8, quindi scansione a passo 4
    pos = next((o for o in range(16, hs - 8, 4)
                if struct.unpack_from("<Q", m, o)[0] == orig_size), None)
    if pos is None:
        # formato LP nuovo (header 256B, Android 16/17): il campo block_device_size
        # non e' piu' nel header; liblp valida le extents contro il device reale
        print("[LP] block_device_size assente nel header (formato nuovo): skip")
    else:
        struct.pack_into("<Q", m, pos, new_size)
        print(f"[LP] block_device_size @header+{pos}: {orig_size} -> {new_size}")

    def parse(ps, es):
        _parts = [tables[ps + i * psz: ps + (i + 1) * psz] for i in range(pc)]
        _exts = []
        for j in range(ec):
            sl = tables[es + j * esz_l: es + (j + 1) * esz_l]
            _exts.append(struct.unpack("<QIQI", sl) if len(sl) == esz_l else (0, 0, 0, 0))
        return _parts, _exts

    parts, exts = parse(ps, es)
    vi = next((i for i, p in enumerate(parts) if p[:36].split(b"\0")[0] == b"vendor_a"), None)
    if vi is None:
        # ripara un run precedente con offsets sbagliati: il blob e' sempre
        # parts@0 + extents@pc*psz + groups + devices
        print("[LP] vendor_a non trovata con gli offset del header: riparo con 0/624")
        ps, es = 0, pc * psz
        parts, exts = parse(ps, es)
        vi = next(i for i, p in enumerate(parts) if p[:36].split(b"\0")[0] == b"vendor_a")
        assert vi is not None, "vendor_a non trovata nemmeno con gli offset noti"
    att, fei, num, grp = struct.unpack_from("<IIII", parts[vi], 36)
    rel_start = swallow_first - s_first
    # dedup + eventuale aggiunta: una sola extent per rel_start (i run
    # precedenti possono averne inserite di duplicate)
    vend = exts[fei:fei + num]
    seen, dedup = set(), []
    for e in vend:
        if e[2] in seen:
            print(f"[LP] dedup: extent duplicata @rel {e[2]} rimossa")
            continue
        seen.add(e[2])
        dedup.append(e)
    if rel_start not in seen:
        dedup.append((new_s_last - swallow_first + 1, 0, rel_start, 0))
        print(f"[LP] aggiunta extent @rel {rel_start}")
    delta = len(dedup) - num
    exts = exts[:fei] + dedup + exts[fei + num:]
    for j in range(len(parts)):
        a2, f2, n2, g2 = struct.unpack_from("<IIII", parts[j], 36)
        if j == vi:
            n2 = len(dedup)
        elif f2 > fei:
            f2 += delta
        parts[j] = parts[j][:36] + struct.pack("<IIII", a2, f2, n2, g2)
    pb = b"".join(parts)
    eb = b"".join(struct.pack("<QIQI", *e) for e in exts)
    gs, gc, gsz = struct.unpack_from("<III", m, 104)
    ds, dc, dsz = struct.unpack_from("<III", m, 116)
    # blob riscritto da capo (RISSACRA gli offset corretti anche se un run
    # precedente li aveva lasciati incoerenti)
    groups = tables[gs:gs + gc * gsz]
    devices = tables[ds:ds + dc * dsz]
    nb = pb + eb + groups + devices
    struct.pack_into("<I", m, 44, len(nb))
    m[48:80] = hashlib.sha256(nb).digest()
    m[hs:hs + len(nb)] = nb
    for o, (s_, c_, z_) in ((80, (0, pc, psz)),
                            (92, (len(pb), len(exts), esz_l)),
                            (104, (len(pb) + len(eb), gc, gsz)),
                            (116, (len(pb) + len(eb) + len(groups), dc, dsz))):
        struct.pack_into("<III", m, o, s_, c_, z_)
    # formato LP nuovo: digest sha256 32B su header con [12:44] azzerato
    m[12:44] = hashlib.sha256(bytes(m[:12]) + bytes(32) + bytes(m[44:hs])).digest()
    with raw.open("r+b") as f:
        f.seek(super_start + 12288)
        f.write(m)
    print(f"[LP] vendor_a: extent @rel {rel_start}+"
          f"{new_s_last - swallow_first + 1} settori "
          f"({(new_s_last - swallow_first + 1) * SECT >> 20} MiB), "
          f"{len(exts)} extents; offsets riscritti "
          f"(parts@{len(pb)}, ext@{len(pb)}, groups@{len(pb) + len(eb)}, "
          f"dev@{len(pb) + len(eb) + len(groups)})")
    print("[OK] estensione completata")


if __name__ == "__main__":
    main()
