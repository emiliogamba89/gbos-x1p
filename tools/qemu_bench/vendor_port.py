#!/usr/bin/env python3
"""Vendor rebuild alla gbos-vm per il recovery mica su QEMU: software KeyMint e
boot-control AOSP sostituiscono hardware assente (protected VM pKVM, TPM, Trusty).
Non modifica mai l'immagine originale: scrive solo nella copia scrivibile.

Pipeline (fedele a skylartaylor/gbos-vm image/make_mica_security_port.py):
  1. estrae il vendor erofs originale dall'immagine recovery (LP metadata)
  2. costruisce overlay.tar PAX con xattr security.selinux per ogni file nuovo
  3. mkfs.erofs --incremental=data --tar=f (erofs-utils >= 1.9) preserva tutto il resto
  4. ripristina lo shared-xattr del root inode e ricalcola il CRC32C del superblock
  5. verifica con fsck.erofs + dump.erofs byte-per-byte
  6. scrive nella copia scrivibile del disco all'offset della partizione vendor

Uso (in WSL, dopo aver compilato erofs-utils 1.9.4):
  python3 vendor_port.py \
    --raw ../../downloads/mica-16471258/android-desktop_signed_recovery_image.bin \
    --cf  ../../downloads/cuttlefish/extract/security \
    --erofs-bin ../../downloads/tools/erofs-1.9.4/bin
"""
import argparse, hashlib, io, json, os, shutil, struct, subprocess, sys, tarfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
VEND = BASE / "downloads" / "mica-16471258"
OUT = VEND / "vendor-port"
WRITABLE = VEND / "disk-writable.raw"

VENDOR_OFF_EXPECT = 5647630336
VENDOR_PARTSIZE_EXPECT = 385949696
ROOT_NID = 54          # vendor mica root inode (nid), come nel boot log
EPOCH = 1230768000


def gpt_partitions(raw):
    """GPT: restituisce {nome: (start_byte, end_byte)} assumendo settori 512B."""
    with open(raw, "rb") as f:
        f.seek(512)
        h = f.read(92)
        assert h[:8] == b"EFI PART", "header GPT"
        ent_lba, num_ents, ent_size = struct.unpack_from("<QII", h, 72)
        out = {}
        for i in range(num_ents):
            f.seek(ent_lba * 512 + i * ent_size)
            e = f.read(ent_size)
            if e[:16] == bytes(16):
                continue
            name = e[56:128].decode("utf-16-le").split("\0")[0]
            first, last = struct.unpack_from("<QQ", e, 32)
            out[name] = (first * 512, (last + 1) * 512)
        return out


def lp_vendor_partition(raw):
    """Parso il metadata LP nella partizione super: restituisce (offset, size) di vendor_a."""
    u = lambda b, o: struct.unpack_from("<I", b, o)[0]
    super_start, super_end = gpt_partitions(raw)["super"]
    super_sectors = (super_end - super_start) // 512
    with open(raw, "rb") as f:
        f.seek(super_start + 4096)
        g = f.read(4096)
        assert u(g, 0) == 0x616c4467, "LP geometry magic"
        f.seek(super_start + 12288)
        m = f.read(u(g, 40))
        assert u(m, 0) == 0x414c5030, "LP metadata magic"
        hs = u(m, 8)
        tables = m[hs:hs + u(m, 44)]
        assert hashlib.sha256(tables).digest() == m[48:80]

        def table(off):
            start, count, size = struct.unpack_from("<III", m, off)
            return [tables[start + i * size:start + (i + 1) * size] for i in range(count)]

        extents = [struct.unpack_from("<QIQI", e) for e in table(92)]
        for p in table(80):
            name = p[:36].split(b"\0")[0].decode()
            _, start, num, _ = struct.unpack_from("<IIII", p, 36)
            if num == 1 and name == "vendor_a":
                e = extents[start]
                # nel mica: (num_sectors, 0, physical_lba_relativo_al_super, data_type)
                if not (0 < e[0] <= super_sectors and e[3] == 0):
                    raise SystemExit(f"extent vendor_a anomalo: {e}")
                return super_start + e[2] * 512, e[0] * 512
    raise SystemExit("vendor_a non trovata nelle dynamic partitions")


def crc32c(data):
    crc = 0xffffffff
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82f63b78 if crc & 1 else 0)
    return crc


def expand_vendor_lp(img, extra_bytes):
    """Aggiunge una seconda extent LP a vendor_a (metadata slot 0) usando un gap
    libero del super. Ritorna (offset_assoluto_extent2, bytes_extent2).
    liblp: extents consecutive per partizione -> shift dei first_extent_index
    successivi; hash sha256 tabelle @48 e checksum header @12 =
    sha256(header[0:12]||32x0||header[44:hs])[:4] LE (formato nuovo LP).
    La slot 1 e' il layout dello slot _b: non viene toccata."""
    u = lambda b, o: struct.unpack_from("<I", b, o)[0]
    super_start, super_end = gpt_partitions(img)["super"]
    with open(img, "rb") as f:
        f.seek(super_start + 12288)
        m = bytearray(f.read(65536))
    hs = u(m, 8)
    tsz = u(m, 44)
    tables = bytes(m[hs:hs + tsz])
    desc = lambda o: struct.unpack_from("<III", m, o)
    ps, pc, psz = desc(80)
    es, ec, esz = desc(92)
    parts = [tables[ps + i * psz: ps + (i + 1) * psz] for i in range(pc)]
    exts = [struct.unpack_from("<QIQI", tables[es + i * esz: es + (i + 1) * esz])
            for i in range(ec)]
    vi = next(i for i, p in enumerate(parts)
              if p[:36].split(b"\0")[0] == b"vendor_a")
    att, fei, num, grp = struct.unpack_from("<IIII", parts[vi], 36)
    assert num >= 1, "vendor_a senza extents"
    last = exts[fei + num - 1]
    vend_end = last[2] + last[0]
    deficit = (extra_bytes + 511) // 512
    # gap fisicamente liberi: salta la zona metadata iniziale e i backup
    # metadata finali (ultimi 256 settori del super)
    rng = sorted((e[2], e[2] + e[0]) for e in exts)
    prev = rng[0][1]  # END del primo extent (non lo start: gap veri tra extent)
    gap = None
    for a, b in rng[1:]:
        if a > prev and prev >= 2048 and a - prev >= deficit and a <= \
                (super_end - super_start) // 512 - 256:
            gap = prev
            break
        prev = max(prev, b)
    if gap is None:
        # coda del super dopo l'ultima extent (nel mica: ~4.6 GiB liberi)
        end_lim = (super_end - super_start) // 512 - 256
        if prev >= 2048 and end_lim - prev >= deficit:
            gap = prev
    assert gap is not None, "nessun gap sufficiente nel super"
    ins = fei + num  # le extents della partizione devono restare contigue
    exts = exts[:ins] + [(deficit, last[1], gap, last[3])] + exts[ins:]
    for j in range(len(parts)):
        a2, f2, n2, g2 = struct.unpack_from("<IIII", parts[j], 36)
        if j == vi:
            n2 = num + 1
        elif f2 > fei:
            f2 += 1
        parts[j] = parts[j][:36] + struct.pack("<IIII", a2, f2, n2, g2)
    pb = b"".join(parts)
    eb = b"".join(struct.pack("<QIQI", *e) for e in exts)
    gs, gc, gsz = desc(104)
    ds, dc, dsz = desc(116)
    groups = tables[gs:gs + gc * gsz]
    devices = tables[ds:ds + dc * dsz]
    nb = pb + eb + groups + devices
    nd = (0, pc, psz)
    ne = (len(pb), len(exts), esz)
    ng = (len(pb) + len(eb), gc, gsz)
    ndev = (len(pb) + len(eb) + len(groups), dc, dsz)
    m2 = bytearray(m)
    m2[44:48] = struct.pack("<I", len(nb))
    m2[48:80] = hashlib.sha256(nb).digest()
    m2[hs:hs + len(nb)] = nb
    for o, d in ((80, nd), (92, ne), (104, ng), (116, ndev)):
        struct.pack_into("<III", m2, o, *d)
    # formato LP nuovo (header 256B, Android 16/17): il checksum del header e'
    # sha256(header[0:12] || 32x0 || header[44:hs])[:4] LE (entrambi i campi
    # @12:16 e @16:44 azzerati nel calcolo; verificato contro il metadata
    # pristine: il crc32 dello schema vecchio NON e' piu' valido)
    # il digest e' 32 byte interi: [12:16] = primi 4, [16:44] = restanti 28
    # (confermato dal disassembly di init: sha256(header con [12:44] azzerato)
    m2[12:44] = hashlib.sha256(bytes(m2[:12]) + bytes(32) + bytes(m2[44:hs])).digest()
    with open(img, "r+b") as f:
        f.seek(super_start + 12288)
        f.write(m2)
    off2 = super_start + gap * 512
    print(f"[LP] vendor_a +{len(exts) - ec} extent: settori {gap}-{gap + deficit} "
          f"({deficit * 512} byte), @ {off2}")
    return off2, deficit * 512


def vendor_extents(img):
    """Lista [(offset_assoluto, bytes)] delle extents LP della partizione vendor_a."""
    super_start, _ = gpt_partitions(img)["super"]
    with open(img, "rb") as f:
        f.seek(super_start + 12288)
        m = f.read(65536)
    u = lambda b, o: struct.unpack_from("<I", b, o)[0]
    hs = u(m, 8)
    tables = m[hs:hs + u(m, 44)]
    ps, pc, psz = struct.unpack_from("<III", m, 80)
    es, ec, esz = struct.unpack_from("<III", m, 92)
    all_ext = [struct.unpack_from("<QIQI", tables[es + j * esz: es + (j + 1) * esz])
               for j in range(ec)]
    for i in range(pc):
        p = tables[ps + i * psz: ps + (i + 1) * psz]
        if p[:36].split(b"\0")[0] == b"vendor_a":
            _, fei, num, _ = struct.unpack_from("<IIII", p, 36)
            return [(super_start + all_ext[fei + k][2] * 512,
                     all_ext[fei + k][0] * 512) for k in range(num)]
    raise SystemExit("vendor_a non trovata")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", required=True, help="immagine recovery mica originale")
    ap.add_argument("--cf", required=True, help="cartella con i file estratti da Cuttlefish")
    ap.add_argument("--erofs-bin", required=True, help="cartella bin di erofs-utils 1.9.4")
    ap.add_argument("--graphics", choices=("virgl", "swiftshader"), default="virgl",
                    help="stack grafico: virgl = Mesa VirGL (ricetta gbos-vm, default); "
                         "swiftshader = ANGLE+SwiftShader CPU (diagnostico)")
    ap.add_argument("--no-diagnostic", action="store_true",
                    help="salta il logger seriale vm-diagnostic-log")
    args = ap.parse_args()

    raw = Path(args.raw)
    cf = Path(args.cf)
    bin_dir = Path(args.erofs_bin)
    dump = bin_dir / "dump.erofs"
    mkfs = bin_dir / "mkfs.erofs"
    fsck = bin_dir / "fsck.erofs"
    for t in (dump, mkfs, fsck):
        if not t.exists():
            raise SystemExit(f"manca {t}: compila erofs-utils 1.9.4 (vedi docs/QEMU-BENCH.md)")
    OUT.mkdir(parents=True, exist_ok=True)

    def run(cmd, **kw):
        return subprocess.run([str(c) for c in cmd], check=True, capture_output=True, **kw)

    def cat_erofs(image, path, off=0):
        return run([dump, f"--offset={off}", "--path=/" + path, "--cat", image]).stdout

    def node_meta(image, path, off=0):
        """metadata inode: (mode, uid, gid, mtime, xattrs{nome:bytes}) via dump.erofs + lettura diretta."""
        path = "/" + path.lstrip("/") if path != "." else "/"
        text = run([dump, f"--offset={off}", "--path=" + path, image]).stdout.decode()
        nid = int([l for l in text.splitlines() if l.startswith("NID:")][0].split()[1])
        with open(image, "rb") as f:
            def rd(pos, n):
                f.seek(off + pos)
                return f.read(n)
            sb = rd(1024, 128)
            bs = 1 << sb[12]
            meta, xbase = struct.unpack_from("<II", sb, 40)
            pos = meta * bs + nid * 32
            i = rd(pos, 64)
            fmt, ic, mode = struct.unpack_from("<HHH", i)
            uid, gid = struct.unpack_from("<II" if fmt & 1 else "<HH", i, 24)
            epoch = struct.unpack_from("<Q", sb, 24)[0]
            mtime = struct.unpack_from("<Q", i, 32)[0] if fmt & 1 else epoch + struct.unpack_from("<I", i, 12)[0]
            x = {}

            def entry(p):
                nl, idx, vl = struct.unpack("<BBH", rd(p, 4))
                b = rd(p + 4, nl + vl)
                prefix = {1: "user.", 4: "trusted.", 6: "security."}.get(idx)
                assert prefix is not None, idx
                x[prefix + b[:nl].decode()] = b[nl:]
                return (4 + nl + vl + 3) & ~3

            if ic:
                p = pos + (64 if fmt & 1 else 32)
                h = rd(p, 12)
                count = h[4]
                for j in range(count):
                    entry(xbase * bs + 4 * struct.unpack("<I", rd(p + 12 + j * 4, 4))[0])
                end = p + 12 + (ic - 1) * 4
                p += 12 + count * 4
                while p < end:
                    p += entry(p)
        return {"mode": mode, "uid": uid, "gid": gid, "mtime": mtime, "xattrs": x}

    # ---------- 1. vendor erofs originale ----------
    off, partsize = lp_vendor_partition(raw)
    assert off == VENDOR_OFF_EXPECT, f"vendor offset inatteso: {off}"
    assert partsize == VENDOR_PARTSIZE_EXPECT, f"vendor partsize inattesa: {partsize}"
    with raw.open("rb") as f:
        f.seek(off + 1024)
        sb = f.read(128)
        assert sb[:4] == bytes.fromhex("e2e1f5e0"), "superblock erofs vendor"
        size_fs = struct.unpack_from("<I", sb, 36)[0] * 4096
        f.seek(off)
        v = OUT / "vendor.orig.erofs"
        v.write_bytes(f.read(size_fs))
    print(f"[1] vendor originale: {v} ({size_fs} byte, off={off}, partsize={partsize})")

    orig = str(v)

    # ---------- 2. file overlay ----------
    files = {}

    def add(name, data, label, mode=0o644):
        files[name] = (data, label, mode)

    def original(path):
        return cat_erofs(orig, path)

    # build.prop: il desktop VM non ha StrongBox (protected VM) hardware
    b = original("build.prop")
    add("build.prop", b + b"\n# The VM has no StrongBox hardware.\n"
        b"ro.vendor.apex.com.android.hardware.keymint.strongbox.desktop=none\n",
        "vendor_file", 0o600)

    # gate sui coprocessori Qualcomm assenti in VM
    n = "etc/init/hw/init.qti.kernel.rc"
    b = original(n)
    old = (b"on post-fs-data\n"
           b"    # Late attach SOCCP and start ADSP and CDSP\n"
           b"    wait_for_prop vendor.all.modules.ready 1\n"
           b"    restart start-subsys")
    assert b.count(old) == 1, "sezione init.qti.kernel.rc non trovata o multipla"
    b = b.replace(old,
        b"# The Qualcomm coprocessors do not exist in a VM.\n"
        b"on post-fs-data && property:ro.boot.vm.qti_subsystems=1\n"
        b"    wait_for_prop vendor.all.modules.ready 1\n"
        b"    restart start-subsys")
    add(n, b, "vendor_configs_file")

    # console seriale per la diagnostica
    n = "etc/selinux/vendor_file_contexts"
    m = node_meta(orig, "/" + n)
    add(n, original(n) + b"\n/dev/ttyAMA0 u:object_r:console_device:s0\n",
        m["xattrs"]["security.selinux"].decode().split(":")[2], m["mode"] & 0o7777)

    # software KeyMint ufficiale Cuttlefish (rust nonsecure)
    add("bin/hw/android.hardware.security.keymint-service",
        (cf / "android.hardware.security.keymint-service.nonsecure").read_bytes(),
        "hal_keymint_default_exec", 0o755)
    # libcrypto privata: non sostituisce quella del vendor usata dagli altri servizi
    add("lib64/vm_keymint/libcrypto.so", (cf / "libcrypto.so").read_bytes(), "vendor_file")
    add("etc/init/vm-software-keymint.rc",
        b"# AOSP software KeyMint: not hardware-backed.\n"
        b"service vendor.keymint-default /vendor/bin/hw/android.hardware.security.keymint-service\n"
        b"    class early_hal\n"
        b"    user nobody\n"
        b"    setenv LD_LIBRARY_PATH /vendor/lib64/vm_keymint:/vendor/lib64\n",
        "vendor_configs_file")

    if not args.no_diagnostic:
        add("etc/init/vm-diagnostic-log.rc",
            b"# Offline VM diagnostics over the emulated UART only.\n"
            b"service vm-diagnostic-log /system/bin/sh -c \"exec /system/bin/logcat -b all -v threadtime *:W keystore2:I init:I apexd:I SystemServer:I ActivityManager:I BootAnimation:I audioadsprpcd:S\"\n"
            b"    class core\n"
            b"    user shell\n"
            b"    group shell log readproc\n"
            b"    seclabel u:r:shell:s0\n"
            b"    console ttyAMA0\n"
            b"# il buffer crash e' piccolo e dedicato: reader veloce, righe non perse\n"
            b"service vm-diagnostic-crash /system/bin/sh -c \"exec /system/bin/logcat -b crash -v threadtime *:V\"\n"
            b"    class core\n"
            b"    user shell\n"
            b"    group shell log readproc\n"
            b"    seclabel u:r:shell:s0\n"
            b"    console ttyAMA0\n"
            b"\n"
            b"on init\n"
            b"    start vm-diagnostic-log\n"
            b"    start vm-diagnostic-crash\n",
            "vendor_configs_file")

    # manifest VINTF per il keymint software
    for n in ("keymint", "secureclock", "sharedsecret"):
        name = f"android.hardware.security.{n}-service.xml"
        add("etc/vintf/manifest/vm-" + name, (cf / name).read_bytes(), "vendor_configs_file")

    # boot-control AOSP: sostituisce l'implementazione che usa le chiamate firmware ChromeOS
    add("bin/hw/android.hardware.boot-service.android-desktop",
        (cf / "boot-service.default").read_bytes(),
        "hal_bootctl_default_exec", 0o755)

    # il VM non ha TPM/Trusty/QSEE: init li riavvierebbe ogni 5 secondi con tombstone.
    # NOTA: questo init NON supporta il comando `disable` in un blocco azione
    # ("Invalid keyword 'disable'"): si usa stop e, per i servizi vendor che
    # ripartono comunque (start espliciti/class_start), si svuota il rc che li
    # definisce — ogni riferimento esterno diventa un no-op innocuo.
    add("etc/init/vm-absent-hardware.rc",
        b"on early-init\n"
        b"    stop android.system.desktop.security.gscd\n"
        b"    stop vendor.secretkeeper.trusty\n"
        b"    stop android.system.desktop.security.pinweaver_storaged\n"
        b"    # diagnostica TEMPORANEA: permissivo (i denial restano nel dmesg seriale)\n"
        b"    setenforce 0\n"
        b"\n"
        b"# udsattestation: il suo rc (system) non e' ancora parsato a early-init\n"
        b"# (stop fallito: 'took 23ms and failed'), serve post-fs-data\n"
        b"on post-fs-data\n"
        b"    stop udsattestation\n"
        b"\n"
        b"# permissivo ANCHE dopo lo switch enforcing di init (il setenforce 0\n"
        b"# early-init viene superato da setenforce 1 su load_all_props):\n"
        b"# tombstoned parte in post-fs-data, a quel punto si ritorna permissivi\n"
        b"on property:init.svc.tombstoned=running\n"
        b"    setenforce 0\n"
        b"\n"
        b"# dump tombstone su console seriale via builtin init (niente shell: init\n"
        b"# rifiuta servizi su /system/bin/sh senza transizione di dominio). I trigger\n"
        b"# coprono stopped e restarting (servizi con autorestart); le copie successive\n"
        b"# colgono i tombstone completi scritti da debuggerd nei cicli precedenti.\n"
        b"on property:init.svc.surfaceflinger=stopped\n"
        b"    write /dev/ttyAMA0 ====SF-STOPPED-TOMBSTONES====\n"
        b"    copy /data/tombstones/tombstone_00 /dev/ttyAMA0\n"
        b"    copy /data/tombstones/tombstone_01 /dev/ttyAMA0\n"
        b"    copy /data/tombstones/tombstone_02 /dev/ttyAMA0\n"
        b"    copy /data/tombstones/tombstone_03 /dev/ttyAMA0\n"
        b"    copy /data/tombstones/tombstone_04 /dev/ttyAMA0\n"
        b"    copy /data/tombstones/tombstone_05 /dev/ttyAMA0\n"
        b"on property:init.svc.surfaceflinger=restarting\n"
        b"    write /dev/ttyAMA0 ====SF-RESTARTING-TOMBSTONES====\n"
        b"    copy /data/tombstones/tombstone_00 /dev/ttyAMA0\n"
        b"    copy /data/tombstones/tombstone_01 /dev/ttyAMA0\n"
        b"    copy /data/tombstones/tombstone_02 /dev/ttyAMA0\n"
        b"    copy /data/tombstones/tombstone_03 /dev/ttyAMA0\n"
        b"    copy /data/tombstones/tombstone_04 /dev/ttyAMA0\n"
        b"    copy /data/tombstones/tombstone_05 /dev/ttyAMA0\n",
        "vendor_configs_file")

    # minkdaemon (Qualcomm SSG): crash-loop su Trusty assente (16+ restart per boot)
    # si conserva solo il mkdir post-fs-data usato dal resto del vendor
    add("etc/init/hlosminkdaemon.rc",
        b"on post-fs-data\n"
        b"    mkdir /data/vendor/qwes 0755 system system\n",
        "vendor_configs_file")

    # qseecomd (QSEE comm daemon): richiede QSEE, assente nel VM
    add("etc/init/qseecomd.rc",
        b"# qseecomd disabilitato nel VM: richiede QSEE/firmware assente\n",
        "vendor_configs_file")

    # weaver HAL (Trusty vsock): assente nel VM; il rc originale dichiara il
    # servizio `disabled` ma viene avviato esplicitamente altrove
    add("etc/init/android.hardware.weaver-service.android-desktop.rc",
        b"# weaver HAL disabilitato nel VM: richiede Trusty/vsock assente\n",
        "vendor_configs_file")

    # minkdaemon (Qualcomm SSG): crash-loop su Trusty assente (16+ restart per boot)
    # si conserva solo il mkdir post-fs-data usato dal resto del vendor
    add("etc/init/hlosminkdaemon.rc",
        b"on post-fs-data\n"
        b"    mkdir /data/vendor/qwes 0755 system system\n",
        "vendor_configs_file")

    # qseecomd (QSEE comm daemon): richiede QSEE, assente nel VM
    add("etc/init/qseecomd.rc",
        b"# qseecomd disabilitato nel VM: richiede QSEE/firmware assente\n",
        "vendor_configs_file")

    # weaver HAL (Trusty vsock): assente nel VM; il rc originale dichiara il
    # servizio `disabled` ma viene avviato esplicitamente altrove
    add("etc/init/android.hardware.weaver-service.android-desktop.rc",
        b"# weaver HAL disabilitato nel VM: richiede Trusty/vsock assente\n",
        "vendor_configs_file")

    # storage_metrics_service (vendor): spamma interface_start per
    # com.google.android.snapshot.ISnapshot/default (HAL assente nel VM, resta
    # solo nel Googlebook reale) ~1x/s -> satura la coda dei control message di
    # init ("Too many pending control messages") -> i ctl.stop/start legitimi di
    # system_server vengono DROPPATI -> main thread bloccato -> Watchdog kill
    # in loop (3 cicli uccisi il 2026-11-07). Si spegne lo spammer.
    add("etc/init/storage_metrics_service.rc",
        b"# storage_metrics disabilitato nel VM: inonda init di ctl.interface_start\n"
        b"# per com.google.android.snapshot.ISnapshot/default (HAL assente) e\n"
        b"# fa droppare i control message legittimi di system_server (Watchdog kill loop)\n",
        "vendor_configs_file")

    # suspend_diagnostics (vendor): polla android.frameworks.stats.IStats/default
    # (HAL assente) -> stesso meccanismo di flooding della coda ctl di init
    add("etc/init/suspend_diagnostics.rc",
        b"# suspend_diagnostics disabilitato nel VM: polla IStats/default assente\n",
        "vendor_configs_file")

    # c2 qti (media codec2 hardware): crash-loopa senza registrare
    # IComponentStore/default; mediaswcodec resta senza 'default' e usa il suo
    # swc2 — svuoto servizio + annuncio VINTF cosi' nessuno lo aspetta
    add("etc/init/vendor.qti.media.c2@1.0-service.rc",
        b"# c2 qti disabilitato nel VM: crash-loopa senza registrare IComponentStore\n",
        "vendor_configs_file")
    add("etc/vintf/manifest/c2_manifest_aidlv2_vendor.xml",
        b"<manifest version=\"1.0\" type=\"device\"/>\n", "vendor_configs_file")

    # ---------- audio alla gbos-vm (mica_audio_port.py): VINTF blanking ----------
    # NOTA: l'APEX audio cuttlefish NON è portabile qui (apexd lo rigetta:
    # 'bootstrap-apexd-failed' + reboot a 28s — la firma/versione non combacia
    # con la nostra piattaforma). Restano solo gli annunci VINTF svuotati: un
    # AIDL sound-trigger annunciato ma assente fa aspettare system_server per
    # sempre ("it trips the watchdog" — commento upstream mica_audio_port.py).
    add("etc/vintf/manifest/bluetooth_audio.xml",
        b"<manifest version=\"1.0\" type=\"device\"/>\n", "vendor_configs_file")
    add("etc/vintf/manifest/soundtrigger.qti.xml",
        b"<manifest version=\"1.0\" type=\"device\"/>\n", "vendor_configs_file")

    # ---------- grafica alla gbos-vm (mica_graphics_port.py): minigbm + DRM composer ----------
    g = HERE.parent.parent / "downloads" / "cuttlefish"
    ex = g / "extract"
    add("bin/hw/android.hardware.composer.hwc3-service.drm",
        (ex / "composer" / "bin" / "hwc3-service.drm").read_bytes(),
        "hal_graphics_composer_default_exec", 0o755)
    # service dell'apex, ripuntato sul vendor (stesso corpo del gbos)
    add("etc/init/android.hardware.composer.hwc3-service.drm.rc",
        b"service vendor.hwcomposer-3 /vendor/bin/hw/android.hardware.composer.hwc3-service.drm\n"
        b"    class hal animation\n"
        b"    interface aidl android.hardware.graphics.composer3.IComposer/default\n"
        b"    user system\n"
        b"    group graphics drmrpc\n"
        b"    capabilities SYS_NICE\n"
        b"    onrestart restart surfaceflinger\n"
        b"    task_profiles ServiceCapacityLow\n",
        "vendor_configs_file")
    # NOTA: niente xml composer3: il mica ha già etc/vintf/manifest/hwc3-drm.xml
    # che dichiara IComposer/default @5; un fragment duplicato rompe il VINTF
    # e il servicemanager rifiuta OGNI add (anche IBootControl -> vold reboot)
    add("lib64/drm_hwcomposer_atom_reporter.so",
        (ex / "composer" / "lib" / "drm_hwcomposer_atom_reporter.so").read_bytes(),
        "same_process_hal_file")
    for n in ("libminigbm_gralloc.so", "libminigbm_gralloc4_utils.so",
              "android.hardware.graphics.allocator-V3-ndk.so",
              "android.hardware.graphics.common-V7-ndk.so"):
        add("lib64/" + n, (ex / "gralloc" / "lib64" / n).read_bytes(), "same_process_hal_file")
    # ANGLE: il loader EGL cerca SOLO /vendor/lib64/egl/libEGL_<ro.hardware.egl>.so;
    # le libs ANGLE di Cuttlefish stanno in system/lib64/ senza subdir egl/, quindi
    # vanno copiate qui sotto lib64/egl/ perche' ro.hardware.egl=angle le trovi.
    # Due varianti grafiche:
    # - virgl (default, ricetta gbos-vm collaudata): Mesa VirGL come EGL/GLES
    #   (virglrenderer su host via virtio-gpu-gl-pci), NIENTE ICD Vulkan
    #   (ro.hardware.vulkan=none), ANGLE disattivato. sf crashava con
    #   ANGLE+SwiftShader (SIGABRT silenzioso ~150-210s dal via).
    # - swiftshader (diagnostico): ANGLE backend vulkan su SwiftShader CPU.
    mesa = HERE.parent.parent / "downloads" / "mesa-virgl"
    if args.graphics == "virgl":
        for n in ("libEGL_virgl.so", "libGLESv1_CM_virgl.so", "libGLESv2_virgl.so"):
            add("lib64/egl/" + n, (mesa / n).read_bytes(), "same_process_hal_file")
        add("lib64/libgallium_dri.so", (mesa / "libgallium_dri.so").read_bytes(),
            "same_process_hal_file")
        add("lib64/libdrm.so", (mesa / "libdrm.so").read_bytes(), "same_process_hal_file")
    else:
        for f in ("libEGL_angle.so", "libGLESv1_CM_angle.so", "libGLESv2_angle.so"):
            add("lib64/egl/" + f,
                (ex / "cf-system" / "system" / "lib64" / f).read_bytes(),
                "same_process_hal_file")
        # SwiftShader: in Android 17 non esiste piu' come EGL/GLES, resta solo l'ICD
        # VULKAN (libvk_swiftshader.so, compilata in locale da build_swiftshader.sh
        # a partire dai sorgenti upstream). Il loader Android la carica dal namespace
        # sphal come vulkan.<ro.hardware.vulkan>.so (stesso meccanismo di vulkan.none);
        # ANGLE gira con backend vulkan SOPRA SwiftShader: catena sf -> angle -> vk-sw.
        # Label: same_process_hal_file (il sphal la accetta, come le libs ANGLE).
        add("lib64/hw/vulkan.swiftshader.so",
            (g / "extract" / "swiftshader" / "libvk_swiftshader.so").read_bytes(),
            "same_process_hal_file", 0o644)
        # stub libandroid.so: vulkan.swiftshader.so dichiara DT_NEEDED libandroid.so
        # ma sphal NON puo' caricare le NDK app libs di sistema -> dlopen falliva
        # ("library libandroid.so not found"). Serve solo AHardwareBuffer_
        # createFromHandle: lo stub ritorna NULL, le altre AHardwareBuffer_* risolvono
        # da libnativewindow (sphal-visible). Costo: niente import AHB via handle.
        add("lib64/libandroid.so",
            (g / "extract" / "swiftshader" / "libandroid.so").read_bytes(),
            "same_process_hal_file", 0o644)
    # sonda EGL: logga i passi della catena display->ANGLE->vulkan su logcat
    # (-> console seriale). Label compositore: dominio con transizione definita.
    add("bin/vm-egltest",
        (g / "extract" / "swiftshader" / "vm-egltest").read_bytes(),
        "hal_graphics_composer_default_exec", 0o755)
    add("etc/init/vm-egltest.rc",
        b"service vendor.vm-egltest /vendor/bin/vm-egltest\n"
        b"    class core\n"
        b"    user root\n"
        b"    group root\n"
        b"    oneshot\n",
        "vendor_configs_file")
    add("bin/hw/android.hardware.graphics.allocator-service.minigbm",
        (ex / "gralloc" / "bin" / "hw" / "android.hardware.graphics.allocator-service.minigbm").read_bytes(),
        "hal_graphics_allocator_default_exec", 0o755)
    add("lib64/hw/mapper.minigbm.so",
        (g / "cf-vendor-files" / "lib64" / "hw" / "mapper.minigbm.so").read_bytes(),
        "same_process_hal_file")
    add("lib64/hw/gralloc.default.so",
        (g / "cf-vendor-files" / "lib64" / "hw" / "gralloc.default.so").read_bytes(),
        "same_process_hal_file")
    # l'allocator minigbm sostituisce quello Qualcomm (SnapAlloc, assente in VM):
    # stesso nome file rc, nuovo binario (come gbos)
    add("etc/init/vendor.qti.hardware.display.allocator-service.rc",
        b"# AOSP minigbm replaces the Qualcomm allocator.\n"
        b"service vendor.graphics.allocator /vendor/bin/hw/android.hardware.graphics.allocator-service.minigbm\n"
        b"    class hal animation\n"
        b"    user system\n"
        b"    group graphics drmrpc\n"
        b"    capabilities SYS_NICE\n"
        b"    onrestart restart surfaceflinger\n"
        b"    task_profiles ServiceCapacityLow\n",
        "vendor_configs_file")
    add("etc/vintf/manifest/vendor.qti.hardware.display.allocator-service.xml",
        b'<manifest version="9.0" type="device"><hal format="aidl"><name>android.hardware.graphics.allocator</name><version>3</version><fqname>IAllocator/default</fqname></hal></manifest>\n',
        "vendor_configs_file")
    add("etc/vintf/manifest/mapper.qti.xml",
        b'<manifest version="9.0" type="device"><hal format="native"><name>mapper</name><fqname>@5.0/minigbm</fqname></hal></manifest>\n',
        "vendor_configs_file")
    # properties grafiche gbos: rimuovi le righe esistenti e riappendedle
    # properties grafiche: virgl = ricetta gbos-vm; swiftshader = ANGLE su CPU.
    # Il backend opengl di ANGLE era fallito: in QEMU virt non c'e' nessun driver
    # GL nativo e SurfaceFlinger abortiva con "no suitable EGLConfig found".
    # hwui/RenderEngine restano su GL in entrambe le varianti.
    if args.graphics == "virgl":
        props = {"ro.hardware.vulkan": "none", "ro.hwui.use_vulkan": "false",
                 "ro.hardware.egl": "virgl", "ro.gfx.angle.supported": "false"}
    else:
        props = {"ro.hardware.vulkan": "swiftshader", "ro.hwui.use_vulkan": "false",
                 "ro.hardware.egl": "angle", "ro.gfx.angle.supported": "true",
                 "debug.angle.backend": "vulkan"}
    props.update({"debug.renderengine.backend": "skiaglthreaded",
             "debug.renderengine.vulkan": "false",
             "debug.renderengine.graphite_desktop_optin": "false",
             "debug.hwui.renderer": "skiagl",
             "ro.vendor.hwcomposer.mode": "client",
             "ro.surface_flinger.has_wide_color_display": "false",
             "ro.surface_flinger.has_HDR_display": "false",
             "ro.vendor.hwc.drop_drm_master": "0"})
    bp = files["build.prop"][0].decode()  # contiene già strongbox=none
    lines = [l for l in bp.splitlines() if l.split("=", 1)[0] not in props]
    lines += ["# VirGL graphics stack (QEMU virtual GPU)."] + [k + "=" + v for k, v in props.items()]
    bp_label, bp_mode = files["build.prop"][1], files["build.prop"][2]
    files["build.prop"] = (("\n".join(lines) + "\n").encode(), bp_label, bp_mode)
    # label sysfs della GPU emulata (path PCI QEMU machine virt)
    n = "etc/selinux/vendor_file_contexts"
    ctx, ctx_label, ctx_mode = files[n]  # contiene già /dev/ttyAMA0
    add(n, ctx + b"/sys/devices/platform/3f000000\\.pcie/pci0000:00/0000:00:01\\.0(/.*)? u:object_r:sysfs_gpu:s0\n",
        ctx_label, ctx_mode)
    add("etc/init/vm-graphics.rc",
        b"# This path is the QEMU virtual GPU only, not host hardware.\n"
        b"on init\n"
        b"    restorecon_recursive /sys/devices/platform/3f000000.pcie/pci0000:00/0000:00:01.0\n"
        b"    start vm-gpu-state\n"
        b"\n"
        b"service vm-gpu-state /system/bin/sh -c \"ls -lZ /dev/dri /sys/class/drm; ls -lZ /sys/bus/pci/devices/0000:00:01.0/; cat /sys/bus/pci/devices/0000:00:01.0/uevent; getprop drm.gpu.vendor_name\"\n"
        b"    disabled\n"
        b"    oneshot\n"
        b"    user shell\n"
        b"    group shell graphics log readproc\n"
        b"    seclabel u:r:shell:s0\n"
        b"    console ttyAMA0\n",
        "vendor_configs_file")

    # ---------- 3. overlay.tar (PAX + xattr selinux) ----------
    # lib QTI display (stack SnapAlloc) orfane: allocator e composer sono sostituiti
    # da minigbm/CF e il mkfs incremental non supporta removal entries (testato su
    # 1.9.4 e sul master: typeflag D ignorato). Le svuotiamo a 0 byte per far
    # spazio alle libs ANGLE (~7 MB). Nessuno dei nostri processi le linka.
    EMPTY_QTI = ["lib64/libgralloc.qti.so", "lib64/libgralloccore.so",
               "lib64/libgrallocutils.so",
               "lib64/libsnapdragoncolor-manager.so", "lib64/libsnapdragoncolor-qdcm.so",
               "lib64/vendor.qti.hardware.display.snapalloc-impl.so",
               "lib64/vendor.qti.hardware.display.snapallocext-V1-ndk.so",
               "lib64/vendor.display.color@1.0.so", "lib64/vendor.display.color@1.1.so",
               "lib64/vendor.display.color@1.2.so", "lib64/vendor.display.color@1.3.so",
               "lib64/vendor.display.color@1.4.so", "lib64/vendor.display.color@1.5.so",
               "lib64/vendor.display.config@1.0.so", "lib64/vendor.display.config@1.1.so",
               "lib64/vendor.display.config@1.2.so", "lib64/vendor.display.config@1.3.so",
               "lib64/vendor.display.config@1.4.so", "lib64/vendor.display.config@1.5.so",
               "lib64/vendor.display.config@1.6.so", "lib64/vendor.display.config@1.7.so",
               "lib64/vendor.display.config@1.8.so", "lib64/vendor.display.config@1.9.so",
               "lib64/vendor.display.config@1.10.so", "lib64/vendor.display.config@1.11.so",
               "lib64/vendor.display.config@2.0.so", "lib64/vendor.display.postproc@1.0.so",
               "lib64/vendor.qti.hardware.display.allocator@1.0.so",
               "lib64/vendor.qti.hardware.display.allocator@3.0.so",
               "lib64/vendor.qti.hardware.display.color-V1-ndk.so",
               "lib64/vendor.qti.hardware.display.composer3-V1-ndk.so",
               "lib64/vendor.qti.hardware.display.composer3-V2-ndk.so",
               "lib64/vendor.qti.hardware.display.composer3-V3-ndk.so",
               "lib64/vendor.qti.hardware.display.composer3-V4-ndk.so",
               "lib64/vendor.qti.hardware.display.composer@1.0.so",
               "lib64/vendor.qti.hardware.display.composer@2.0.so",
               "lib64/vendor.qti.hardware.display.demura-V1-ndk.so",
               "lib64/vendor.qti.hardware.display.mapper@1.0.so",
               "lib64/vendor.qti.hardware.display.mapper@1.1.so",
               "lib64/vendor.qti.hardware.display.mapper@2.0.so",
               "lib64/vendor.qti.hardware.display.mapper@3.0.so",
               "lib64/vendor.qti.hardware.display.mapper@4.0.so",
               "lib64/vendor.qti.hardware.display.mapperextensions@1.0.so",
               "lib64/vendor.qti.hardware.display.mapperextensions@1.1.so",
               "lib64/vendor.qti.hardware.display.mapperextensions@1.2.so",
               "lib64/vendor.qti.hardware.display.mapperextensions@1.3.so",
               "lib64/vendor.qti.hardware.display.postproc-V1-ndk.so"] + [
               "lib64/vendor.qti.hardware.display.config-V" + str(i) + "-ndk.so"
               for i in range(1, 18)]
    for n in EMPTY_QTI:
        add(n, b"", "vendor_lib_file")
    new_dirs = ["lib64/vm_keymint"]
    base_dirs = [".", "bin", "bin/hw", "etc", "etc/init", "etc/init/hw", "etc/selinux",
                 "etc/vintf", "etc/vintf/manifest", "lib64", "lib64/hw", "lib64/egl"]
    dirs = base_dirs + new_dirs
    with tarfile.open(OUT / "overlay.tar", "w", format=tarfile.PAX_FORMAT) as t:
        for n in dirs:
            if n in new_dirs:
                m = {"mode": 0o40755, "uid": 0, "gid": 2000, "mtime": EPOCH,
                     "xattrs": {"security.selinux": b"u:object_r:vendor_file:s0"
                                if n.startswith("lib64") else b"u:object_r:vendor_configs_file:s0"}}
            else:
                m = node_meta(orig, n)
            ti = tarfile.TarInfo(n)
            ti.type = tarfile.DIRTYPE
            ti.mode = m["mode"] & 0o7777
            ti.uid = m["uid"]
            ti.gid = m["gid"]
            ti.mtime = m["mtime"]
            ti.pax_headers = {} if n == "." else {
                "SCHILY.xattr." + k: val.decode() for k, val in m["xattrs"].items()}
            t.addfile(ti)
        for n, (b, label, mode) in files.items():
            ti = tarfile.TarInfo(n)
            ti.size = len(b)
            ti.mode = mode
            ti.uid = 0
            ti.gid = 0
            ti.mtime = EPOCH
            ti.pax_headers = {"SCHILY.xattr.security.selinux": f"u:object_r:{label}:s0"}
            t.addfile(ti, io.BytesIO(b))
    print(f"[3] overlay.tar: {len(dirs)} dir + {len(files)} file")

    # ---------- 4. mkfs incremental ----------
    vend = OUT / "vendor.erofs"
    shutil.copyfile(v, vend)
    run([mkfs, "--incremental=data", "--tar=f", "-x0", "-b4096",
         f"-T{EPOCH}", "-zlz4hc", vend, OUT / "overlay.tar"])
    # mkfs incremental tar import clears root xattrs, and cannot grow this inode.
    # Ripristino il riferimento shared-xattr esatto del root inode (nid 54).
    with raw.open("rb") as f:
        f.seek(off + ROOT_NID * 32)
        old = f.read(48)
    with vend.open("r+b") as f:
        f.seek(ROOT_NID * 32)
        new = f.read(48)
        assert old[2:4] == new[2:4] and not (old[0] & 1 or new[0] & 1)
        f.seek(ROOT_NID * 32 + 32)
        f.write(old[32:48])
        # CRC32C copre i primi 4 KiB meno il checksum field
        f.seek(1024)
        b = bytearray(f.read(3072))
        b[4:8] = bytes(4)
        f.seek(1028)
        f.write(struct.pack("<I", crc32c(b)))
    print(f"[4] vendor.erofs: {vend.stat().st_size} byte "
          f"({100 * vend.stat().st_size // partsize}% della partizione)")

    # ---------- 5. verifica ----------
    run([fsck, vend])
    for n, (b, label, mode) in files.items():
        got = cat_erofs(str(vend), n)
        assert got == b, f"mismatch dopo mkfs: {n}"
    for p in ("/etc/init/hw/init.android-desktop.rc", "/etc/selinux/precompiled_sepolicy"):
        assert cat_erofs(str(vend), p) == cat_erofs(orig, p), f"file originale cambiato: {p}"
    for n in dirs:
        if n in new_dirs:
            continue
        got = node_meta(str(vend), n)
        want = node_meta(orig, n)
        assert got == want, f"metadata dir cambiata: {n}"
    print("[5] verifica fsck + byte-per-byte: OK")

    # ---------- 6. copia scrivibile + scrittura vendor ----------
    if not WRITABLE.exists():
        print(f"[*] creo la copia scrivibile del disco ({raw.stat().st_size >> 20} MiB)...")
        subprocess.run(["cp", "--sparse=always", str(raw), str(WRITABLE)], check=True)
    vend_size = vend.stat().st_size
    ext_list = vendor_extents(WRITABLE)
    total = sum(b for _, b in ext_list)
    if vend_size > total:
        expand_vendor_lp(WRITABLE, vend_size - total)
        ext_list = vendor_extents(WRITABLE)
        total = sum(b for _, b in ext_list)
    assert vend_size <= total, f"vendor.erofs ({vend_size}) > partizione ({total})"
    data = vend.read_bytes()
    pos = 0
    with WRITABLE.open("r+b") as f:
        for o, sz in ext_list:
            if pos >= vend_size:
                break
            chunk = data[pos:pos + sz]
            f.seek(o)
            f.write(chunk)
            if len(chunk) < sz:  # pad coda ultima extent
                f.write(bytes(sz - len(chunk)))
            pos += sz
    print(f"[6] vendor patchato scritto in {WRITABLE.name} @ " +
          " + ".join(str(o) for o, _ in ext_list) +
          f" ({len(ext_list)} extents)")

    manifest = {
        "source": "official Android CI 16373615 software KeyMint + boot-service.default",
        "vendor_offset": off,
        "vendor_partition_bytes": partsize,
        "vendor_bytes": vend.stat().st_size,
        "root_nid": ROOT_NID,
        "files": {n: {"sha256": hashlib.sha256(b).hexdigest(), "label": label,
                      "mode": oct(mode)} for n, (b, label, mode) in files.items()},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print("[OK]", OUT / "manifest.json")


if __name__ == "__main__":
    main()
