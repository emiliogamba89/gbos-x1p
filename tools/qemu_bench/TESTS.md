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

## Stato 2026-11-05 — ICD SwiftShader carica; sf ancora SIGABRT silenzioso

### Risolto in questa sessione
1. **`dlopen vulkan.swiftshader.so` falliva nel namespace sphal** in cascata:
   - `libandroid.so not found` (sphal non carica le NDK app libs): stub
     `lib64/libandroid.so` (build_libandroid_stub.sh) con
     `AHardwareBuffer_createFromHandle` -> NULL;
   - `cannot locate symbol _Z9sync_waitii` (libsync piattaforma non nei NEEDED):
     `sync_wait(int,int)` reimplementata nello stub (poll POLLIN sul fence fd);
   - `cannot locate symbol __android_log_write` (liblog non in sphal): no-op
     nello stub. Tutto in un solo .so, soname libandroid.so, label
     same_process_hal_file.
2. **servizi assenti in crash-loop eliminati**: questo init NON supporta
   `disable` ne' `setenforce` come keyword rc ("Invalid keyword"). Svuotati i
   rc che definiscono hlosminkdaemon/qseecomd/weaver-service (start espliciti
   altrove diventano no-op); weaver era il tipc-abort loop.
3. **sonda EGL nel guest** (vm-egltest.c, dominio compositore): eglInitialize +
   eglChooseConfig PASSANO (exit 0) -> ANGLE/ICD inizializzano. NB: il dominio
   compositore NON legge default_prop/graphics_config_prop (avc denials).
4. **logcat->seriale**: e' il NOSTRO servizio vm-diagnostic-log
   (logcat -b all ... *:W) - il buffer crash e' incluso, quindi il messaggio
   d'abort di sf NON passa da logd per niente.

### Aperto: SurfaceFlinger SIGABRT silenzioso a ~150-210s dal via
- deterministico su ogni istanza, thread secondario (nome ereditato
  "surfaceflinger"), nessun output logcat di sf;
- persiste con debug.sf.disable_client_composition=1 -> NON e' RenderEngine;
- swiftshader release: DABORT == warn (NON aborta) -> l'abort non e' swiftshader;
- compatibile con: CHECK ANGLE (android_set_abort_message, solo tombstone)
  oppure sf-watchdog (main thread bloccato su composer/vsync - virtio-gpu non
  ha vblank);
- il tombstone e' inaggungibile: crash_dump riceve SIGALRM (30s) prima di
  finire sotto TCG; setenforce 0 non e' disponibile nel rc.

### Prossimi passi
1. ipotesi watchdog/composer: provare ro.vendor.hwcomposer.mode=... alternativi
   e/o escludere il vsync (debug.sf.scheduler...) e/o hwc3-drc senza vulkan;
2. oppure rebuild SwiftShader debug (DCHECK_ALWAYS_ON + SWIFTSHADER_DISABLE_TRACE
   disattivo) e ANGLE con logging forzato per far uscire il messaggio su logcat;
3. oppure velocizzare il dump: crash_dump < 30s (piu' vCPU? -smp 8) per avere
   il tombstone (i trigger copy tombstone_00..03 su init.svc.surfaceflinger
   stopped/restarting sono gia' nel rc vm-absent-hardware.rc);
4. il boot DIVERSAMENTE avanza fino ai servizi (keystore2 attende
   boot_completed; userdata formattata; composer/allocator registrati).

## Svolta 2026-11-05 (2) — virtio-gpu-gl-pci funziona; percorso gbos-vm definitivo

### Trovato il riferimento che FUNZIONA
`downloads/reference-gbos-vm/` e' la ricetta completa (macOS/hvf) gia' collaudata:
- QEMU: `-device virtio-gpu-gl-pci,hostmem=8G,blob=true,venus=true` + spice gl=es
  (run/run_vm.py:98) + un virgl_render_server lato host;
- vendor (image/mica_graphics_port.py:8,40): **Mesa VirGL** come EGL
  (ro.hardware.egl=virgl, libEGL_virgl/libGLESv1_CM_virgl/libGLESv2_virgl/
  libgallium_dri/libdrm), **ro.hardware.vulkan=none** (NIENTE ICD Vulkan),
  ro.gfx.angle.supported=false, RenderEngine skia-GL (identico al nostro);
- build-guest.sh: Mesa cross-compilata con meson per Android aarch64
  (api 35, llvm=disabled, glx/gbm=disabled, platforms=android).

### Cosa abbiamo gia' ottenuto nel banco WSL
- QEMU Debian 8.2.2 AArch64 HA virtio-gpu-gl-pci (modulo hw-display-virtio-gpu-pci-gl.so);
  richiede LD_PRELOAD=/usr/lib/aarch64-linux-gnu/qemu/ui-opengl.so (definisce
  qemu_egl_display; egl-headless NON basta perche' non init EGL display);
  display: -display gtk,gl=on (finestra WSLg su X11; egl-headless fallisce:
  manca /dev/dri render node su WSL, c'e' solo /dev/dxg);
- il guest ora negozia **+virgl, cap sets: 2 (virgl id1 + venus id2)**
  (prima: -virgl, cap sets: 0 col device plain);
- sf crasha IDENTICO anche con virgl -> il crash e' nel vendor stack
  ANGLE+SwiftShader, NON nel device QEMU.

### Piano definitivo (prossima sessione)
1. Adattare build-guest.sh a WSL/Linux: bison da apt, meson via pip venv,
   NDK r27c locale (~/Android/android-ndk-r27c), sysroot shim come per
   SwiftShader; output atteso: libEGL_virgl.so, libGLESv1_CM_virgl.so,
   libGLESv2_virgl.so, libgallium_dri.so, libdrm.so (+ eventuale venus).
2. vendor_port: nuova variante grafica "gbos-vm" che replica mica_graphics_port.py
   (file Mesa in lib64/egl + lib64, props virgl/none/angle=false) — gia' uno
   switch 1:1 perche' il resto (minigbm, composer drc, keymint software) e'
   comune.
3. Test: sf dovrebbe superare init/display/composizione senza crash; poi
   boot_completed + launcher.
4. Ricaduta utile: venus (Vulkan guest->host) disponibile per dopo senza
   ricompilare QEMU.

