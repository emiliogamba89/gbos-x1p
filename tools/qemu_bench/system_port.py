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
    return crc ^ 0xffffffff

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--patched", required=True)
    ap.add_argument("--erofs-bin", required=True)
    args = ap.parse_args()
    bin_dir = Path(args.erofs_bin)
    dump, mkfs, fsck = bin_dir / "dump.erofs", bin_dir / "mkfs.erofs", bin_dir / "fsck.erofs"
    raw = Path(args.raw).resolve()
    patched_jar = Path(args.patched).resolve()
    jar_bytes = patched_jar.read_bytes()

    out = VEND / "system-port"
    out.mkdir(exist_ok=True)
    orig = out / "system.orig.erofs"
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
    print("[3] overlay.tar pronto")

    new = out / "system.new.erofs"
    shutil_copy(orig, new)
    run([mkfs, "--incremental=data", "--tar=f", "-x0", "-b4096",
         f"-T{EPOCH}", "-zlz4hc", new, out / "overlay.tar"])
    # NOTA: l'incrementale non libera i blocchi dei file sostituiti, quindi
    # l'immagine cresce oltre SYSTEM_SIZE: extend_system.py ha gia' aggiunto
    # una seconda extent da 24 MiB a system_a e la scrittura spezza l'immagine.
    print(f"[4] system.erofs: {new.stat().st_size} byte")

    # fixup root inode: mkfs tar-import cancella gli xattr del root dir.
    # root_nid nel superblock @1024+16 (u16). L'inode e' a root_nid*32 dall'inizio
    # immagine; i byte [32:48] sono l'unione con il riferimento shared-xattr.
    def root_nid(img):
        with img.open("rb") as f:
            f.seek(1024)
            sb = f.read(64)
        assert sb[:4] == bytes.fromhex("e2e1f5e0"), "magic erofs"
        return struct.unpack_from("<H", sb, 16)[0]

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
    assert cat("/system/framework/framework-res.apk") == run([dump, "--offset=0", "--path=/system/framework/framework-res.apk", "--cat", str(orig)]).stdout, "framework-res cambiato"
    print("[6] verifica OK: jar patchato presente, resto invariato")

    manifest = {
        "system_offset": SYSTEM_OFF, "system_size": SYSTEM_SIZE,
        "ext2_offset": EXT2_OFF, "ext2_size": EXT2_SIZE,
        "new_size": new.stat().st_size,
        "services_jar_sha256": hashlib.sha256(jar_bytes).hexdigest(),
        "patch": "Watchdog.mAllowRestart true->false (services.jar classes.dex, 1 byte)",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # scrittura nel disco: system_a ora ha DUE extents (extend_system.py):
    # chunk1 = i primi SYSTEM_SIZE byte @ SYSTEM_OFF, chunk2 = il resto @ EXT2_OFF
    ext2_off, ext2_size = EXT2_OFF, EXT2_SIZE
    with new.open("rb") as f:
        data = f.read()
    assert len(data) <= SYSTEM_SIZE + ext2_size,         f"immagine troppo grande anche con l'extent extra: {len(data)}"
    with raw.open("r+b") as f:
        f.seek(SYSTEM_OFF)
        f.write(data[:SYSTEM_SIZE])
        resto = data[SYSTEM_SIZE:]
        if resto:
            assert len(resto) <= ext2_size
            f.seek(ext2_off)
            f.write(resto)
            print(f"[7] chunk2: {len(resto)} byte @ {ext2_off}")
    print(f"[OK] system patchata scritta in {raw.name} @ {SYSTEM_OFF}")

def shutil_copy(src, dst):
    with src.open("rb") as a, dst.open("wb") as b:
        while True:
            chunk = a.read(1 << 24)
            if not chunk:
                break
            b.write(chunk)

if __name__ == "__main__":
    main()
