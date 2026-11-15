#!/usr/bin/env python3
"""Ricostruisce la partizione system del mica con services.jar patchato
(Watchdog mAllowRestart=false: in TCG il readPackageLPw tiene main occupato
per minuti e il Watchdog 60s uccide system_server a ciclo continuo).
Stessa meccanica di vendor_port.py: mkfs.erofs --incremental + tar overlay.
Uso (in WSL):
  python3 system_port.py --raw ../../downloads/mica-16471258/disk-writable.raw \
      --patched /tmp/sjar/services-patched.jar \
      --erofs-bin ../../downloads/tools/erofs-1.9.4/bin
"""
import argparse, hashlib, io, json, struct, subprocess, sys, tarfile
from pathlib import Path

VEND = Path(__file__).resolve().parent
WRITABLE = Path("downloads/mica-16471258/disk-writable.raw").resolve()
SYSTEM_OFF = 177209344
SYSTEM_SIZE = 1081446400
EXT2_OFF = 8273694720   # seconda extent di system_a (extend_system.py)
EXT2_SIZE = 24 * 1024 * 1024
EPOCH = 1230768000  # 2009-01-01, come immagine originale

def run(cmd, **kw):
    print("[cmd]", " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode != 0:
        print(r.stdout.decode(errors="replace")[-2000:])
        print(r.stderr.decode(errors="replace")[-2000:])
        raise SystemExit(f"comando fallito: {cmd[0]}")
    return r

def crc32c(data):
    crc = 0xffffffff
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82f63b78 if crc & 1 else 0)
    return crc  # EROFS uses CRC32C(~0, data) without a final XOR.

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--patched", required=False)
    ap.add_argument("--erofs-bin", required=True)
    ap.add_argument("--reuse", action="store_true",
                    help="riusa system.new.erofs gia' costruito (salta la build)")
    args = ap.parse_args()
    bin_dir = Path(args.erofs_bin)
    dump, mkfs, fsck = bin_dir / "dump.erofs", bin_dir / "mkfs.erofs", bin_dir / "fsck.erofs"
    raw = Path(args.raw).resolve()

    out = VEND / "system-port"
    out.mkdir(exist_ok=True)
    orig = out / "system.orig.erofs"

    def write_system(raw, data):
        """Scrive l'immagine system_a; se serve, estende la partizione LP
        con l'algoritmo collaudato del vendor (extend_system_lp.py)."""
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from extend_system_lp import extend_partition, lp_extents
        ext_list = lp_extents(raw, "system_a")
        total = sum(s for _, s in ext_list)
        if len(data) > total:
            off2, size2 = extend_partition(raw, "system_a", len(data) - total)
            ext_list = lp_extents(raw, "system_a")
            total = sum(s for _, s in ext_list)
        assert len(data) <= total, f"immagine {len(data)} > partizione {total}"
        pos = 0
        with raw.open("r+b") as f:
            for off, sz in ext_list:
                chunk = data[pos:pos + sz]
                f.seek(off)
                f.write(chunk)
                if len(chunk) < sz:
                    f.write(bytes(sz - len(chunk)))
                pos += len(chunk)
        print(f"[OK] system ({len(data)} byte) scritta su {len(ext_list)} extents: {ext_list}")

    if args.reuse:
        new = out / "system.new.erofs"
        assert new.exists() and (out / "manifest.json").exists(), \
            "--reuse: manca system.new.erofs (prima esegui la build completa)"
        data = new.open("rb").read()
        write_system(raw, data)
        return

    assert args.patched, "serve --patched <services.jar patchato> senza --reuse"
    patched_jar = Path(args.patched).resolve()
    jar_bytes = patched_jar.read_bytes()
    # Catch invalid patch output before touching the large EROFS image/disk.
    import zipfile
    from dex_checksums import verify_dex
    with zipfile.ZipFile(io.BytesIO(jar_bytes)) as jar:
        dex_names = [name for name in jar.namelist() if name.endswith('.dex')]
        assert dex_names, 'services.jar contains no DEX files'
        for name in dex_names:
            assert verify_dex(jar.read(name)), f'Invalid DEX checksums: {name}'
    if not orig.exists():
        with raw.open("rb") as f:
            f.seek(SYSTEM_OFF)
            data = f.read(SYSTEM_SIZE)
        orig.write_bytes(data)
    print(f"[1] system originale: {orig.stat().st_size} byte")

    def meta(path):
        """(mode, uid, gid, nid) di un path nel system originale"""
        r = run([dump, "--offset=0", "--path=" + path, str(orig)])
        text = r.stdout.decode(errors="replace")
        mode = uid = gid = nid = None
        for line in text.splitlines():
            if line.startswith("NID:"):
                nid = int(line.split()[1])
            elif line.startswith("Uid:"):
                # il dump mette Uid, Gid e Access sulla stessa riga
                uid = int(line.split()[1])
                for tok in line.split():
                    if tok.startswith("Access:") or "/" in tok and tok[0] in "01234567dl" and tok != line.split()[1]:
                        pass
                import re
                m = re.search(r"Access:\s*(\d+)/", line)
                if m:
                    mode = int(m.group(1), 8)
                m2 = re.search(r"Gid:\s*(\d+)", line)
                if m2:
                    gid = int(m2.group(1))
        return mode, uid, gid, nid, text

    fm = meta("/system/framework")
    jm = meta("/system/framework/services.jar")
    print(f"[2] framework: mode={fm[0]:o} uid={fm[1]} nid={fm[3]} | jar: uid={jm[1]} nid={jm[3]}")

    # overlay tar: il tar NON puo' modificare i meta del root dir esistente,
    # quindi includo solo la dir framework e il jar (i meta vengono dall'originale)
    label = "u:object_r:system_file:s0"
    with tarfile.open(out / "overlay.tar", "w", format=tarfile.PAX_FORMAT) as t:
        ti = tarfile.TarInfo("system")
        ti.type = tarfile.DIRTYPE
        ti.mode = 0o755
        ti.uid, ti.gid, ti.mtime = 0, 0, EPOCH
        ti.pax_headers = {"SCHILY.xattr.security.selinux": label}
        t.addfile(ti)
        ti = tarfile.TarInfo("system/framework")
        ti.type = tarfile.DIRTYPE
        ti.mode = fm[0] & 0o7777
        ti.uid, ti.gid, ti.mtime = fm[1], fm[2], fm[3] if False else EPOCH
        ti.pax_headers = {"SCHILY.xattr.security.selinux": label}
        t.addfile(ti)
        ti = tarfile.TarInfo("system/framework/services.jar")
        ti.size = len(jar_bytes)
        ti.mode = jm[0] & 0o7777
        ti.uid, ti.gid, ti.mtime = jm[1], jm[2], EPOCH
        ti.pax_headers = {"SCHILY.xattr.security.selinux": label}
        t.addfile(ti, io.BytesIO(jar_bytes))

    # sostituisce NotoColorEmoji.ttf (215 MB NON compressi su disco) con un
    # font piccolo VALIDO (AndroidClock.ttf): libera spazio per la crescita
    # dell'incrementale; si perde il rendering emoji, il resto resta.
    emoji_meta = meta("/system/fonts/NotoColorEmoji.ttf")
    clock_bytes = run([dump, "--offset=0", "--path=/system/fonts/AndroidClock.ttf", "--cat", str(orig)]).stdout
    # TTC minimalista: la config font cita gli stub con index>0 (i .ttc
    # originali hanno piu' subface per peso/lingua) e la copia in
    # /data/fonts/config sopravvive tra i boot: un TTF a faccia singola
    # fa lanciare IllegalArgumentException -> FontManagerService_create
    # muore senza complete() -> onBootPhase resta in join() -> boot fermo.
    # ttcf con 4 offset tutti validi: qualunque index risolve (tofu CJK).
    _sfnt_off = 12 + 16
    cjk_bytes = (b"ttcf" + struct.pack(">II", 0x00010000, 4)
                 + struct.pack(">4I", *([_sfnt_off] * 4)) + clock_bytes)
    assert struct.unpack_from(">4I", cjk_bytes, 12) == (_sfnt_off,) * 4
    assert cjk_bytes[_sfnt_off:_sfnt_off + 4] == clock_bytes[:4]
    print(f"[2b] emoji stub: {len(clock_bytes)} byte (era 215 MB)")
    with tarfile.open(out / "overlay.tar", "a", format=tarfile.PAX_FORMAT) as t:
        ti = tarfile.TarInfo("system/fonts")
        ti.type = tarfile.DIRTYPE
        ti.mode = 0o755
        ti.uid, ti.gid, ti.mtime = 0, 0, EPOCH
        ti.pax_headers = {"SCHILY.xattr.security.selinux": label}
        t.addfile(ti)
        ti = tarfile.TarInfo("system/fonts/NotoColorEmoji.ttf")
        ti.size = len(clock_bytes)
        ti.mode = emoji_meta[0] & 0o7777
        ti.uid, ti.gid, ti.mtime = emoji_meta[1], emoji_meta[2], EPOCH
        ti.pax_headers = {"SCHILY.xattr.security.selinux": label}
        t.addfile(ti, io.BytesIO(clock_bytes))
        # anche i CJK ttc (~46MB su disco): il limite e' la partizione system_a
        # originale (l'incrementale non compatta), non servono estensioni LP
        cjk_meta = meta("/system/fonts/NotoSansCJK-Regular.ttc")
        for cjk in ("NotoSansCJK-Regular.ttc", "NotoSerifCJK-Regular.ttc"):
            cm = meta(f"/system/fonts/{cjk}")
            ti = tarfile.TarInfo(f"system/fonts/{cjk}")
            ti.size = len(cjk_bytes)
            ti.mode = cm[0] & 0o7777
            ti.uid, ti.gid, ti.mtime = cm[1], cm[2], EPOCH
            ti.pax_headers = {"SCHILY.xattr.security.selinux": label}
            t.addfile(ti, io.BytesIO(cjk_bytes))
        print("[2c] stub CJK: NotoSansCJK + NotoSerifCJK")
    # fonts.xml: gli stub CJK sono TTF a faccia singola ma le famiglie li
    # citano con index>0 (i .ttc originali hanno piu' subface): Font.Builder
    # lancia IllegalArgumentException -> il task FontManagerService_create
    # muore SENZA complete() -> onBootPhase resta in mServiceStarted.join()
    # per sempre e il boot si blocca. Rimuoviamo le famiglie puntanti agli
    # stub: zero costo di spazio, nessun file nuovo da aggiungere.
    import xml.etree.ElementTree as ET
    fx_bytes = run([dump, "--offset=0", "--path=/system/etc/fonts.xml",
                    "--cat", str(orig)]).stdout
    fx_meta = meta("/system/etc/fonts.xml")
    STUBS = {'NotoSansCJK-Regular.ttc', 'NotoSerifCJK-Regular.ttc'}
    fx_root = ET.fromstring(fx_bytes)
    fx_gone = []
    for fam in list(fx_root):
        names = {el.text.strip() for el in fam.findall("font") if el.text}
        if names & STUBS:
            fx_gone.append(fam.get("name") or fam.get("lang") or "?")
            fx_root.remove(fam)
    assert fx_gone, "fonts.xml: famiglie CJK stub non trovate"
    fx_out = (b'<?xml version="1.0" encoding="utf-8"?>\n'
              + ET.tostring(fx_root, encoding="utf-8"))
    print(f"[2d] fonts.xml: rimosse {len(fx_gone)} famiglie: {fx_gone}")
    # rc system-side: i trigger su init.svc.* da rc VENDOR sono vietati
    # ("unexported property trigger") e audioserver/timberslide/ssgmigd/
    # udsattestation sono servizi SYSTEM: gli stop retriggerati vivono qui.
    # audioserver: SIGSEGV in loop senza HAL audio (QEMU: nessun /dev/snd,
    # CONFIG_SND_VIRTIO assente) -> 74+ crash -> sys.init.updatable_crashing=1
    # -> init riavvia zygote e tutto il mondo Java prima di boot_completed.
    # udsattestation: si blocca in attesa di IGsc/default (GSC assente in VM).
    im = meta("/system/etc/init")  # meta della dir esistente (riferimento)
    zz = (b"\n# --- VM fixes (appended) ---\n"
          b"# MARKER di build: se questa riga appare sulla seriale, il system\n"
          b"# patchato e' quello montato dal guest\n"
          b"on init\n"
          b"    write /dev/ttyAMA0 ===VM-SYSTEM-BUILD4-MARKER===\n"
          b"\n"
          b"# audioserver: SIGSEGV in loop senza HAL audio -> crash counter ->\n"
          b"# updatable_crashing -> init riavvia zygote e il mondo Java.\n"
          b"on property:init.svc.audioserver=running\n"
          b"    stop audioserver\n"
          b"\n"
          b"# udsattestation: si blocca in attesa di IGsc/default (GSC assente)\n"
          b"on property:init.svc.android.system.desktop.security.udsattestation=running\n"
          b"    stop android.system.desktop.security.udsattestation\n"
          b"\n"
          b"on property:init.svc.timberslide=running\n"
          b"    stop timberslide\n"
          b"\n"
          b"on property:init.svc.ssgqmigd=running\n"
          b"    stop ssgqmigd\n")
    ar_meta = meta("/system/etc/init/audioserver.rc")
    ar = run([dump, "--offset=0", "--path=/system/etc/init/audioserver.rc",
              "--cat", str(orig)]).stdout
    with tarfile.open(out / "overlay.tar", "a", format=tarfile.PAX_FORMAT) as t:
        # Explicit parents: implicit tar directories lose their SELinux labels.
        for directory in ("system/etc", "system/etc/init"):
            dm = meta('/' + directory)
            ti = tarfile.TarInfo(directory)
            ti.type = tarfile.DIRTYPE
            ti.mode = dm[0] & 0o7777
            ti.uid, ti.gid, ti.mtime = dm[1], dm[2], EPOCH
            ti.pax_headers = {"SCHILY.xattr.security.selinux": label}
            t.addfile(ti)
        ti = tarfile.TarInfo("system/etc/fonts.xml")
        ti.size = len(fx_out)
        ti.mode = fx_meta[0] & 0o7777
        ti.uid, ti.gid, ti.mtime = fx_meta[1], fx_meta[2], EPOCH
        ti.pax_headers = {"SCHILY.xattr.security.selinux": label}
        t.addfile(ti, io.BytesIO(fx_out))
        ti = tarfile.TarInfo("system/etc/init/zz-vm-fixes.rc")
        ti.size = len(zz)
        ti.mode = 0o644
        ti.uid, ti.gid, ti.mtime = 0, 0, EPOCH
        ti.pax_headers = {"SCHILY.xattr.security.selinux": label}
        t.addfile(ti, io.BytesIO(zz))
        # Redundant copy in a known rc. The old missing-file symptom was
        # caused by dm-verity/FEC serving original blocks, NOT init enumeration.
        ti = tarfile.TarInfo("system/etc/init/audioserver.rc")
        ti.size = len(ar) + len(zz)
        ti.mode = ar_meta[0] & 0o7777
        ti.uid, ti.gid, ti.mtime = ar_meta[1], ar_meta[2], EPOCH
        ti.pax_headers = {"SCHILY.xattr.security.selinux": label}
        t.addfile(ti, io.BytesIO(ar + zz))
    print("[3] overlay.tar pronto (+zz-vm-fixes.rc, +trigger in audioserver.rc)")

    new = out / "system.new.erofs"
    shutil_copy(orig, new)
    run([mkfs, "--incremental=data", "--tar=f", "-x0", "-b4096",
         f"-T{EPOCH}", "-zlz4hc", new, out / "overlay.tar"])
    # NOTA: l'incrementale non libera i blocchi dei file sostituiti, quindi
    # l'immagine cresce oltre SYSTEM_SIZE: extend_system.py ha gia' aggiunto
    # una seconda extent da 24 MiB a system_a e la scrittura spezza l'immagine.
    print(f"[4] system.erofs: {new.stat().st_size} byte")

    # fixup root inode: mkfs tar-import cancella gli xattr del root dir.
    # Resolve through dump.erofs: +16 in the superblock is inos, NOT root_nid
    # (+14 for this format). Do not corrupt unrelated inode/data bytes.
    def root_nid(img):
        text = run([dump, '--path=/', str(img)]).stdout.decode()
        return int(next(line for line in text.splitlines()
                        if line.startswith('NID:')).split()[1])

    rn_old, rn_new = root_nid(orig), root_nid(new)
    print(f"[5] root nid old={rn_old} new={rn_new}")
    with orig.open("rb") as f:
        f.seek(rn_old * 32)
        old = f.read(48)
    with new.open("r+b") as f:
        f.seek(rn_new * 32)
        new_b = f.read(48)
        assert old[2:4] == new_b[2:4] and not (old[0] & 1 or new_b[0] & 1), \
            "formato inode root diverso dal previsto"
        # Preserve the new data address/layout, but restore root ownership/mode
        # and the original shared-xattr reference cleared by tar import.
        f.seek(rn_new * 32 + 4)
        f.write(old[4:6])
        f.seek(rn_new * 32 + 24)
        f.write(old[24:28])
        f.seek(rn_new * 32 + 32)
        f.write(old[32:48])
        # CRC32C del primo 4KiB del superblocco senza il campo checksum
        f.seek(1024)
        b = bytearray(f.read(3072))
        b[4:8] = bytes(4)
        f.seek(1028)
        f.write(struct.pack("<I", crc32c(b)))

    # verifica: fsck + il jar patchato e' li' e i file chiave sono invariati
    run([fsck, str(new)])
    def cat(path):
        return run([dump, "--offset=0", "--path=" + path, "--cat", str(new)]).stdout
    got = cat("/system/framework/services.jar")
    assert got == jar_bytes, "services.jar patchato non combacia"
    assert cat("/system/fonts/NotoColorEmoji.ttf") == clock_bytes, "emoji stub non combacia"
    assert cat("/system/fonts/NotoSansCJK-Regular.ttc") == cjk_bytes, "stub CJK non combacia"
    assert cat("/system/fonts/NotoSerifCJK-Regular.ttc") == cjk_bytes, "stub CJK non combacia"
    got_fx = cat("/system/etc/fonts.xml")
    assert ('NotoSansCJK-Regular.ttc'.encode() not in got_fx
            and 'NotoSerifCJK-Regular.ttc'.encode() not in got_fx), \
        "fonts.xml ancora con famiglie CJK stub"
    assert cat("/system/framework/framework-res.apk") == run([dump, "--offset=0", "--path=/system/framework/framework-res.apk", "--cat", str(orig)]).stdout, "framework-res cambiato"
    print("[6] verifica OK: jar patchato presente, resto invariato")

    manifest = {
        "system_offset": SYSTEM_OFF, "system_size": SYSTEM_SIZE,
        "new_size": new.stat().st_size,
        "services_jar_sha256": hashlib.sha256(jar_bytes).hexdigest(),
        "patch": "Watchdog.mAllowRestart true->false (services.jar classes.dex, 1 byte)",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # scrittura nel disco: se l'incrementale cresce oltre system_a, la
    # partizione viene estesa nel super con l'algoritmo collaudato del vendor
    with new.open("rb") as f:
        data = f.read()
    write_system(raw, data)

def shutil_copy(src, dst):
    with src.open("rb") as a, dst.open("wb") as b:
        while True:
            chunk = a.read(1 << 24)
            if not chunk:
                break
            b.write(chunk)

if __name__ == "__main__":
    main()
