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

## RISOLTO 2026-11-05 (3) — il crash di sf era il caricatore EGL in sphal

La root cause di TUTTI i crash di SurfaceFlinger era una sola: **il
caricatore EGL lato sf non riusciva a caricare il driver GL dal namespace
sphal** e sf abortiva ("couldn't find an OpenGL ES implementation" /
"no suitable EGLConfig"):
- ANGLE+SwiftShader: dlopen falliva in cascata (libandroid.so, sync_wait,
  __android_log_write non raggiungibili in sphal — risolti con lo stub
  libandroid.so) ma il crash rimaneva;
- Mesa VirGL (build WSL, build_mesa_*.sh): falliva su libc++_shared.so
  -> refuso del mio cross-file: la ricetta gbos-vm usa -static-libstdc++
  (libc++ statica, zero dipendenze runtime). Ripristinato il flag.

### Variante grafica virgl (default) in vendor_port.py
`--graphics virgl` (default) vs `--graphics swiftshader` (diagnostico):
- libs: lib64/egl/{libEGL,libGLESv1_CM,libGLESv2}_virgl.so + libgallium_dri.so
  + libdrm.so (downloads/mesa-virgl/, ~17.7 MB il gallium) — label
  same_process_hal_file
- props: ro.hardware.egl=virgl, ro.hardware.vulkan=none,
  ro.gfx.angle.supported=false (identici a mica_graphics_port.py)

### Boot verificato (run 45 min, poi chiuso per timeout)
- zygote 565s, sf 709s: ZERO crash (prima moriva a ~160-210s dal via)
- bootanim AVVIATA da sf (pid dedicato, usa IAllocator) = stack grafico
  end-to-end funzionante (sf -> RenderEngine skia-GL su Mesa VirGL ->
  gralloc minigbm -> composer drc -> scanout)
- system_server partito ~2200s (36 min wall sotto TCG), inizializzava i
  servizi di sistema quando lo script ha chiuso per timeout
- avvio QEMU con GL: virtio-gpu-gl-pci richiede LD_PRELOAD ui-opengl.so
  e -display gtk,gl=on (egl-headless senza /dev/dri non parte su WSL)

### Da fare
- run lungo (boot_long.bat, WAIT_SECONDS=5400) fino a boot_completed + UI
- dopo la conferma: ripristinare le performance (TCG resta lento; valuta
  -smp 6/8 e l'eventuale venus per Vulkan guest)

## Stato 2026-11-06 — grafica RISOLTA; rimane la corsa contro il Watchdog

### Confermato su run lunghi (2+ ore di guest)
- SurfaceFlinger con Mesa VirGL: **ZERO crash in tutto il run** (prima moriva
  a 160-210s costanti). sf orchestra il boot (avvia bootanim), presenta e
  resta stabile per ore. Problema grafico CHIUSO.
- bootanim parte (pid dedicato, usa IAllocator) e disegna nella finestra GTK.
- system_server parte (~2100-2300s guest) ma sotto TCG i suoi boot phase
  superano i timeout del Watchdog (60s/thread): dopo vari ANR il Watchdog
  uccide system_server ("Watchdog: *** GOODBYE!") -> zygote lo riavvia ->
  nuovo ciclo di ~30-40 min. boot_completed non raggiunto per questo.

### Leve per il prossimo tentativo (in ordine di costo)
1. **fermare audioserver** (SIGSEGV loop: null deref, crash+dump ogni pochi
   min: spreco di CPU) — svuotare il rc audio nel vendor come per minkdaemon;
2. **-smp 6** (host 8 core; MTTCG attivo e verificato: qemu al 227%);
3. valutare l'eliminazione di altri SEGV-loop (verificare a 2h di log);
4. watchdog: nessun prop standard per allungarlo; restano i fattori di velocita'.
5. venus (Vulkan guest->host via virtio-gpu) gia' negoziato dal device per il futuro.

### File/variante
- vendor_port.py --graphics virgl (default) | swiftshader (diagnostico)
- boot_long.bat: WAIT_SECONDS=99999 (QEMU non viene piu' ucciso dal wrapper)
- mesa libs: downloads/mesa-virgl/ (build da build_mesa_gles.sh, flag
  -static-libstdc++ essenziale per il sphal)

## Stato 2026-11-09 — ripristino LP pulito e nuovo run VirGL

- Il disco scrivibile preesistente era in uno stato LP incerto dopo i tentativi
  di estendere `system_a`. Prima di intervenire ne è stata salvata una copia
  byte-per-byte in `/home/zero89/disk-writable-before-recovery.raw`.
- `disk-writable.raw` è stato ripristinato dall'immagine recovery ufficiale
  (SHA256 verificato identico: `b0fd614ffe1a088fa3451a4b81c55a73f83e246286184a46ca306250db9af1f1`)
  e `vendor_port.py --graphics virgl` è stato rieseguito da zero. Verifica
  `fsck.erofs + byte-per-byte` superata; l'estensione LP vendor è stata
  aggiunta dalla procedura già collaudata.
- Nuovo run: zygote ~254s, SurfaceFlinger ~327s, bootanim avviata; VirGL resta
  attivo. `system_server` parte, ma il primo avvio TCG resta molto lento e il
  Watchdog lo termina dopo ~37 minuti; zygote riparte. **`sys.boot_completed`
  non è stato osservato**, quindi UI/boot completo non confermati.
- Il tentativo di ricostruire `system` con `system_port.py` si è fermato prima
  della scrittura: immagine EROFS incrementale 1,103,167,488 byte contro
  1,081,446,400 disponibili. Gli stub dei font non riducono gli extent già
  allocati dall'incrementale.
- Il QEMU di questo run è stato fermato; seriale salvata in
  `qemu-serial.log` (20 MiB). La copia pre-ripristino è una salvaguardia, non
  un layout LP da riutilizzare: l'estensione system non è stata convalidata.
- Prossimo lavoro: evitare di ritentare `lp_rewrite_slots.py` (parser errato);
  usare un metodo EROFS compatto oppure implementare/verificare l'estensione
  `system_a` partendo dai metadati LP puliti. Solo allora riprovare la patch
  Watchdog. Grafica e partenza di zygote/SF sono già provate separatamente.

## Stato 2026-11-15 — AVB/FEC sbloccato; rebuild EROFS e DEX corretti

**Confermato nel guest, non solo dedotto dalle immagini:**

- Ripristinate esclusivamente `vbmeta_a/b` (4 MiB ciascuna) dalla recovery
  ufficiale su `/home/zero89/disk-run.raw`, poi impostato `flags=3` a offset
  **120, big endian**. Magic header `AVB0`; `AVBf` è il footer. Il vecchio
  `dump_vbmeta.py` aveva un layout completamente errato, ora corretto.
- Backup delle partizioni prima/ufficiale/test in
  `/home/zero89/avb-backups/20261115-121243-366058/`.
- Log: `Returning avb_handle with status: VerificationDisabled`, poi
  `AVB HASHTREE disabled on: /system` e sulle altre partizioni AVB.
  Nessun errore/correzione FEC. `veritymode=logging` da solo NON disabilita FEC;
  è il flag nella vbmeta integra a farlo. Non azzerare la vbmeta.
- Il primo mount raw ha rivelato il CRC EROFS errato di `system_port.py`:
  EROFS usa CRC32C seed `~0`, **senza XOR finale**. Corretto.
- Successivo blocco SELinux: root directory unlabeled. Il rebuild leggeva
  `root_nid` da +16 (in realtà `inos`); il root reale è NID **57**, ora risolto
  con `dump.erofs --path=/`. Ripristinati xattr condivisi, mode e uid/gid root;
  aggiunti label espliciti ai parent `system`, `system/etc`, `system/etc/init`.
- Nuova system: **1,103,175,680 byte**, scritta negli stessi tre extent LP,
  `fsck.erofs` e confronto services.jar/framework-res superati.
- Nel guest: parsing di `zz-vm-fixes.rc` a 14.60s, marker
  `===VM-SYSTEM-BUILD4-MARKER===` a 108s; **`stop audioserver` succeeded** a
  344s, stop udsattestation succeeded a 407s. Nessun restart zygote fino a quel punto.
  La precedente ipotesi che init non enumerasse i nuovi rc era falsa: FEC
  restituiva i blocchi originali.
- ART ha poi rivelato `Bad checksum` su services.jar: il patcher v3 calcolava
  SHA-1 su `[12:]` anziché `[32:]` e Adler32 prima di aggiornare la firma.
  Corretto: SHA-1 `[32:]`, poi Adler32 `[12:]`; ZIP stored allineato a 4 byte.
  Riparato `/home/zero89/services-v3.jar` preservando le patch istruzioni;
  tutti e quattro i DEX verificati, system ricostruita e nuovo run avviato.
- Nel run con DEX corretti, `SystemServer: Entered the Android system server!`
  alle 11:37:19 guest, PID **1070**, poi `Reading configuration...`.
  Nessun `Bad checksum` / `VerifyError` osservato; marker e stop audio nuovamente
  confermati. Run lasciato attivo per il boot lungo TCG.
- `validate_avb_fix.sh`: **7 test unitari passati**, parser concorde con avbtool
  sulla vbmeta ufficiale (digest header+aux MATCH), compilazione Python e sintassi
  shell OK. Guard contro QEMU concorrente provato: rifiuto prima di ruotare il log.
- **BOOT COMPLETATO (2026-11-15, run 20:13→20:28): `sys.boot_completed=1`,
  launcher3 attivo (PID 2073), azioni post-boot eseguite.** Prima volta
  assoluta su QEMU/TCG con la system ufficiale patchata.

### Root cause finale del boot bloccato (post AVB/DEX)

- Gli stub CJK (`NotoSansCJK-Regular.ttc`, `NotoSerifCJK-Regular.ttc`) erano
  TTF a faccia singola (AndroidClock), ma le famiglie in `fonts.xml` li citano
  con `index="0..3"`: `Font.Builder.nBuild` lancia `IllegalArgumentException`
  → il task `FontManagerService_create` muore SENZA `complete()` →
  `onBootPhase` resta in `mServiceStarted.join()` (FontManagerService.java:194)
  → main thread fermo per sempre (il Watchdog, con le kill NOPpate, urlava
  `*** GOODBYE!` ogni ~70s senza potere agire: 336 volte in 7 ore).
- **`fonts.xml` nuovo NON basta**: `UpdatableFontDir` copia la config in
  `/data/fonts/config/config.xml` al primo load e la riusa ai boot successivi:
  lo stale config (con le famiglie CJK) continuava a far fallire il task.
- Fix DOPPIO in `system_port.py`: (1) `fonts.xml` ricostruito senza le 4
  famiglie CJK (`zh-Hans`, `zh-Hant,zh-Bopo`, `ja`, `ko`) → 179 famiglie,
  0 riferimenti CJK, XML valido; (2) gli stub CJK sono ora **TTC validi**
  (`ttcf`, versione 0x00010000, 4 offset tutti verso lo stesso sfnt valido →
  qualunque `index` risolve) così anche lo stale `/data` config parser.
- Verificato con dump dal disco: `fonts.xml` nuovo = 179 famiglie / 0 CJK;
  TTC estratti == `cjk_bytes` (assert end-to-end nel rebuild).
- Nel run finale: NESSUN `Failure in FontManagerService_create`; il main
  thread attraversa per la prima volta tutti i boot phase (AMS, AppSearch,
  Thermal, Content…) → `sys.boot_completed=1` → launcher3 up.
- Residuo (non bloccante): SIGABRT di init (PID 437) a ~46s dal lancio,
  prima del framework; emoji senza glifi (stub AndroidClock); CJK = tofu.

### Lezioni

- Gli stub sostitutivi devono avere le STESSE proprietà strutturali degli
  originali citati dalla config (ttc collection ⇒ subface multiple).
- Tutto ciò che scrive in `/data` sopravvive ai rebuild di system/vendor:
  valutare sempre lo stato persistente (font config, ART cache, settings).
- Il TTC wrap (28 byte di header + sfnt riusato) è la tecnica universale
  per stub di collection font.
- Gli edit dei file grandi vanno fatti con ancore estratte a runtime + od
  post-verify: le omissioni di battitura sui token lunghi sono inevitabili.

### Comandi riproducibili (QEMU spento prima di scrivere)

```bash
python3 tools/qemu_bench/restore_vbmeta_test.py /home/zero89/disk-run.raw \
  downloads/mica-16471258/android-desktop_signed_recovery_image.bin --flags 3 --apply
bash tools/qemu_bench/rebuild_system_avb_fix.sh
python3 tools/qemu_bench/test_avb_helpers.py
```

`restore_vbmeta_test.py` controlla GPT, salva backup e verifica read-back;
omettere `--apply` per dry run; `--flags 0 --apply` ripristina le vbmeta ufficiali.
Non riscrive `super` né `/data`. `stop_qemu.sh` ora cerca argv, non `comm`
(troncato a 15 caratteri su Linux); `run_qemu.sh` rifiuta QEMU concorrenti
prima di ruotare il log. Seriale live: `/home/zero89/qemu-serial-live.log`.

---

## USB bring-up nativo su ThinkBook (Fase 2, 2026-11-21)

Obiettivo: primo boot reale del kernel mica sul ThinkBook 16 G7 QOY via USB,
senza console seriale. Catena: UEFI → GRUB arm64 → kernel GKI mica + DTB
mainline Lenovo + initrd probe → log su partizione FAT "BOOTLOG" → poweroff.

Scoperte chiave:
- `boot_a` della recovery è vuoto (kernel_size=0, ramdisk=0) e NESSUNA
  partizione della recovery contiene un DTB base: sul Dell la base DT la fornisce
  il bootloader di fabbrica (assente dall'immagine). `dtb_a` è tutto zeri;
  `dtbo_a` è una tabella overlay valida (`d7b7ab1e`) ma inutile senza base.
- Il kernel mica (6.12.81-android16) ha `CONFIG_EFI_STUB=y`, `CONFIG_OF=y`,
  FAT/USB/xHCI/UAS built-in, `CONFIG_ACPI` assente → boot obbligatoriamente DT.
- Il ThinkBook ha il device tree nel mainline:
  `arch/arm64/boot/dts/qcom/x1p42100-lenovo-thinkbook-16.dts` (kernel 6.17+;
  tastiera/touchpad/display PWM/NVMe/WCN7850/audio/USB). Le distro ARM girano
  già su questa macchina con GRUB+DT: catena provata, replicata col kernel mica.
- Il vendor initramfs mica include `camcc-x1p42100.ko` → la famiglia supporta
  esplicitamente il SoC X1P42100.

Artefatti (tutti in `tools/qemu_bench/`):
- `build_dtb_lenovo.sh` — compila il DTB da sorgente kernel 6.18 (kernel.org,
  estrazione selettiva; cpp -nostdinc + dtc senza kbuild; i symlink dt-bindings
  richiedono anche `include/uapi`). Output `/home/zero89/gbos-usb/dtb-lenovo.dtb`
  (152 KiB, root compatible `"lenovo,thinkbook-16","qcom,x1p42100"`).
- `usb-test/probe.c` — init statico: monta proc/sys/devtmpfs, aspetta
  l'enumerazione USB, crea il node `/dev/sda2`, dump DT model/compatible +
  cpuinfo + partizioni + meminfo + dmesg completo in
  `/BOOTLOG/gbos-probe.log`, poi poweroff.
- `build_usb_test.sh` — assembla `usbdisk.img` (1,34 GiB): MBR bootable;
  p1 FAT32 "GRUB" 256 MiB (BOOTAA64.EFI standalone + kernel.bin +
  dtb-lenovo.dtb + initrd probe; grub.cfg: `linux /gbos/kernel.bin
  rdinit=/probe printk.devkmsg=on ignore_loglevel` + `devicetree
  /gbos/dtb-lenovo.dtb`); p2 FAT32 "BOOTLOG" 1 GiB. Toolchain senza root:
  `apt download` + `dpkg-deb -x` (grub-common, grub-efi-arm64-bin, mtools,
  device-tree-compiler); nota: i .deb scaricati hanno nome con versione →
  usare glob `${p}_*.deb`.
- `build_grub_efi.sh` — BOOTAA64.EFI via `grub-mkimage` con memdisk
  (`grub-mkstandalone` richiede libefivar non scaricabile via apt senza root;
  su Ubuntu arm64 il comando `devicetree` è nel modulo **fdt.mod**).
- `write_usb.ps1` — scrittura raw su `\\.\PhysicalDrive2` con verifica
  FriendlyName Kingston e transcript `write_usb-log.txt`; richiede UAC.

Stato: `usbdisk.img` scritto sulla chiavetta Kingston DataTraveler 3.0
(31 GB); in attesa del primo boot reale (Secure Boot off, F12 → UEFI:
Kingston). Canale di verifica: `gbos-probe.log` dentro BOOTLOG.
Il log assente = kernel morto prima dell'initrd (probabile mismatch DT) →
iterare sul DTB. Il log presente = kernel vivo: leggere model/compatible/
cpuinfo/partizioni per la Fase 3 (disco GPT Android completo su USB).

### Fix boot console GRUB (2026-11-21, secondo round)

Sintomo: sul ThinkBook appare la console GRUB invece del menu.
Cause trovate e corrette:
1. Il memdisk non veniva montato: mancano **memdisk.mod** e **tar.mod** nel
   core image → device `(memdisk)` inesistente → `$prefix/grub.cfg` non
   trovato → console. Fix: moduli aggiunti a `grub-mkimage`.
2. `initrd-probe.cpio.gz` veniva scritto in `$W/` invece che in
   `$W/esp/gbos/` → non finiva nell'ESP (il `linux` del menu avrebbe
   comunque fallito). Fix: path corretto + `search --set=root --label GRUB`
   nella cfg (dischi builtin nel kernel GRUB arm64-efi; `efidisk.mod` NON
   esiste nel pacchetto Ubuntu arm64).
3. Verifica in QEMU con AAVMF (`qemu-efi-aarch64`, disco come nvme):
   menu → auto-boot 1s → `EFI stub: Booting Linux Kernel...` — catena
   GRUB→kernel→DTB→initrd validata end-to-end (su `-M virt` il kernel mica
   si ferma dopo, normale: non è hardware X1P).

### Fix probe (2026-11-21, terzo round): log mancante su hardware

Il probe non è mai stato testato prima (in QEMU il boot usava il vendor
initramfs). Due bug trovati e corretti, validati in QEMU col kernel mica
reale + usb-storage emulato (`test_probe_qemu.sh`):

1. **cpio handwritten sbagliato**: campo `c_mode` al posto di `c_uid` e
   trailer malformato (`b'0'*120` invece dei 13 campi da 8) → il kernel NON
   riconosceva l'initramfs e passava al path legacy initrd → panic
   `Unable to mount root fs` e `/probe` mai eseguito. Fix: generazione con
   `cpio -o -H newc` reale (deb senza root, come gli altri tool).
2. **polling rotto nel probe**: dopo `mknod`, `stat(/dev/sda2)` è sempre
   vero (il nodo esiste come file) → il probe apriva il device prima che
   lo scan SCSI registrasse le partizioni → `Can't open blockdev` → poweroff
   senza log. Fix: polling su `/proc/partitions` (riga `sda2`), max 30 s;
   nel log ora compare `sda2 registrato dal kernel: SI/NO`.

Verifica QEMU completa: `Run /probe as init process` → `sda: sda1 sda2`
a ~3.4 s → mount FAT → `gbos-probe.log` scritto in BOOTLOG (DT model,
compatible, cpuinfo, partitions, dmesg) → poweroff. Kernel mica su virt:
`CONFIG_MSDOS_PARTITION=y`, `CONFIG_DEVTMPFS` assente (mknod manuale
corretto). Il probe gira quindi anche senza devtmpfs.

Avvio del test su hardware: ora il log DEVE comparire in BOOTLOG. Se
`sda2 registrato: NO` → il disco USB non è sda su quel hardware (cambiare
device nel probe). Se BOOTLOG resta vuota → il kernel muore prima del
mount dell'initramfs (probabile early-boot DT mismatch) → iterare sul DTB.

