# QEMU bench — matrice dei test (aggiornata al 2026-11-01)

Il payload `initrd_q2.img` = initrd originale + override cpio (ultimo membro
vince sui path). Si genera con `python tools/qemu_bench/build_override.py`
(attenzione: il file attualmente contiene la lista di test `[icc-clk.ko]`).

## Come lanciare un test (WSL2 Ubuntu)

```bash
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
WAIT_SECONDS=240 bash run_qemu.sh q1   # payload originale, cmdline Q1
WAIT_SECONDS=240 bash run_qemu.sh q2   # payload con override, cmdline Q2
bash run_qemu.sh q3                    # variante kvm-arm.mode=nvhe
```

Il log seriale finisce in `qemu-serial.log`; lo script si autotermina al primo
`reboot:` del guest o allo scadere di `WAIT_SECONDS`.

## Risultati

| Test | Payload | Esito |
|---|---|---|
| Q1 | originale | **OK**: kernel boota, init first stage parte, 5 moduli poi reboot 'bootloader' |
| Override 6 moduli | override `modules.load` ridotto | identico al Q1: **l'init non usa quel file** |
| Override vuoto | `modules.load` + `modules.load.recovery` vuoti | identico: confermato |
| kvm-arm.mode=nvhe | cmdline q3 | KVM in nVHE ma lista identica |
| Override `[icc-clk.ko]` | lista da 1 modulo | identico: confermato |

## Causa trovata (storia corretta)

1. Il vendor_boot contiene **2 frammenti taggati**: `platform` (kind=1) e
   `recovery` (kind=2, 60 MB). Il frammento recovery contiene
   `modules.load.recovery` (108 moduli Qualcomm): **l'init leggeva QUEL file**
   (recovery mode di default), per questo gli override su `modules.load` erano
   ignorati.
2. La **bootconfig** nascosta nel vendor_boot (`androidboot.hardware=android-desktop`,
   `androidboot.load_modules_parallel=true`) non veniva passata da QEMU.
3. Il super del recovery È popolato (vendor erofs @5647630336+1024,
   system_dlkm @8188329984+1024: il superblock EROFS sta a +1024, non
   allineato a 4096 - il primo check era un falso negativo).
4. **Config kernel estratta (IKCONFIG)**: `CONFIG_EFI_STUB=y` (F1 confermata),
   `CONFIG_VIRTIO_PCI=m`, `CONFIG_VIRTIO_BLK=m` (moduli da system_dlkm).

## Milestone v3 (stile gbos-vm)

`build_initrd_v3.py` ricompone l'initrd come blob gzip unico:
`platform cpio + init cpio + override` (frammento recovery SCARTATO);
cmdline con tutti gli `androidboot.*`; disco recovery su virtio-blk RO;
GICv3. Per il disco servono i moduli virtio firmati da system_dlkm:
`sudo apt install erofs-utils && bash extract_virtio.sh` (in WSL), poi
`python build_initrd_v3.py` (su Windows, incorpora i moduli) e `run_qemu.sh v3`.

## Stato 2026-11-04 — vendor SwiftShader: boot AVB/liblp sbloccati, attesa boot_completed

Risolto il blocco per cui il boot moriva a ~24s con `init` exit(127):

1. **`[liblp] Logical partition metadata has invalid checksum`**: il formato LP
   del mica e' un formato nuovo (header 256 byte, Android 16/17), NON quello
   AOSP v1.2:
   - `tables_size` @44, `tables_hash` (sha256) @48:80 — come prima;
   - il checksum del header e' **sha256(header con [12:44] azzerato)[:32]**:
     i campi @12:16 (4 byte) e @16:44 (28 byte) SONO INSIEME un unico digest
     sha256 da 32 byte (4+28), verificato dal disassembly di init
     (tools/qemu_bench/disasm_liblp.py). Il vecchio codice scriveva solo i
     primi 4 byte lasciando gli altri 28 stantii -> mismatch.
   - `block_device_size` NON esiste piu' nel header (validazione contro il
     device reale).
2. **`avb_slot_verify failed, result: 6` (INVALID_METADATA)**: causato da
   vendor bytes scritti sopra `vbmeta_a` durante l'esperimento di estensione
   "assorbita" del super. Ripristinati i contenuti di vbmeta_a/b, init_boot_a/b,
   vendor_boot_a/b dall'immagine originale (vbmeta intatto = AVB passa).
3. **`expand_vendor_lp` non trovava il gap**: la ricerca ignorava la CODA del
   super dopo l'ultima extent (nel mica: ~4.6 GiB liberi). Fix: check finale
   `end_lim - prev >= deficit`.
4. **build SwiftShader** completata (49 MB aarch64 Android): fix link
   `-landroid -lnativewindow -Wl,--no-as-needed` (AHardwareBuffer_*
   risolti a runtime via DT_NEEDED, `--no-undefined` rimosso), wrapper compiler
   che filtra `--target`/`--sysroot` (il driver clang Android usa il PRIMO
   --target e cmake produceva un triple senza API -> crtbegin non trovato),
   shim STL legacy con symlink al sysroot r27c. Integrazione:
   `lib64/hw/vulkan.swiftshader.so` + `ro.hardware.vulkan=swiftshader` +
   ANGLE backend vulkan (l'opengl falliva: nessun driver GL nativo in virt).
5. **spazio vendor**: vendor.erofs 408 MB > extents originali (386 MB):
   espansione LP nel gap di coda del super (22523904 byte @rel 15699896),
   checksum riscritti col formato nuovo. `extend_super.py`/`reset_super_meta.py`
   (GPT absorb) NON servono piu': restano come reference.
6. **servizi assenti in crash-loop** (minkdaemon x16, pinweaver x7, weaver x6,
   qseecomd x3): `vm-absent-hardware.rc` ora usa `disable` oltre a `stop`
   (disable previene anche gli start manuali/class_start; nota: `stop` da solo
   non basta perche' il mica li avvia esplicitamente).

### Stato raggiunto
Boot pulito fino ai servizi vendor (keystore2 in attesa di boot_completed,
zygote non ancora avviato a ~700s): il boot TCG e' lento e vold/restorecon /data
su userdata fresca (4.3 GB) costa minuti. Serve una finestra >25 min.

### Prossimo passo (WSL risponde lento/wedged: riavviare WSL come admin)
```
WRITABLE_DISK=1 WAIT_SECONDS=2700 bash run_qemu.sh v3
```
Il disco e' pronto: metadata LP validi (checksum corretti), vendor con
SwiftShader+ANGLE+minigbm scritto su 2 extents, userdata/metadata azzerate.

