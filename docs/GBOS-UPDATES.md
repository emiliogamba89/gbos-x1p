# Aggiornamenti ufficiali Googlebook OS (tracking)

> Scopo: tracciare gli aggiornamenti upstream di Googlebook OS e le implicazioni
> per gbos-x1p (kernel, driver, slot A/B, criteri per un eventuale rebase del
> recovery usato come base).

## 2026-11-06 — Aggiornamento novembre 2026, build CL3B.260622.286.R2

Fonti: [TuttoAndroid — changelog novembre 2026](https://www.tuttoandroid.net/news/2026/11/06/googlebook-aggiornamento-novembre-2026-changelog-1181400/)
(fork delle release note ufficiali; thread Reddit `r/Googlebook` `1xowmi0`).

### Contenuto principale

- Distribuzione graduale a **tutti e 5 i modelli** (Acer 14, ASUS 14, Lenovo 15,
  HP 14, Dell XPS 13); base Android 17; rilascio graduale via OTA
  (Impostazioni > Sistema > Aggiornamenti software).
- Patch di sicurezza **2026-11-01** (~60 CVE, bollettino Android).
- **Kernel**: fix di stabilità **Linux 6.18** sui modelli x86 [1][2][3];
  il kernel **6.12** dei modelli ARM64 HP/Dell [4][5] riceve patch di sicurezza
  Android 16, correzioni DisplayPort USB-C, fix crash del **watchdog
  sospensione/ripresa del display**, HDCP 1.x Multi-Stream DP.
  → conferma indiretta che la famiglia ARM64 (mica/quartz) resta su **GKI 6.12**,
  coerente col nostro 6.12.81-android16.
- **3–6 GB di RAM risparmiati** per il multitasking su tutti i modelli.
- Fix installazione firmware che riportava dispositivi [4][5] al firmware di
  avvio di fabbrica, con riavvii imprevisti.
- Fix **priorità slot A/B**: gli aggiornamenti interrotti non causano più boot
  loop — conferma che lo slot priority è parte del flusso update ufficiale.
- Input: tasti post-sospensione su schermata di blocco; tastiera/touchpad più
  reattivi dopo cambio form factor [1] (Acer).
- Video/GPU: fix crash del driver display su unplug di hub USB-C o MST
  daisy-chain [4][5]; fix DRM esterni (Netflix schermo nero / pausa >5 s),
  HDR/HLG 60 FPS.
- BT/audio: riconnessione automatica mouse BLE, routing ASHA (apparecchi acustici),
  microfoni/interfacce USB esterni (Focusrite Scarlett, Elgato Wave) senza
  problemi di buffering; fix sync labiale su cuffie BT.
- **Terminale Linux (BETA)**: VM Linux persistente al resume, porte TCP
  inoltrate stabili (SSH :2222), aggiornamenti in-place delle config VM senza
  reset dello storage Linux.

### Implicazioni per gbos-x1p

1. **Il nostro recovery (mica 16471258) non è l'ultima build.** La
   CL3B.260622.286.R2 porta il kernel 6.12 aggiornato con fix DisplayPort USB-C
   e fix watchdog display. Se il porting nativo si blocca proprio su questi
   due temi, conviene scaricare il nuovo recovery mica e ri-applicare le
   patch — sono tutte scriptate (`system_port.py`, `vendor_port.py`,
   `rebuild_initrd_v4.py`, `restore_vbmeta_test.py`), quindi il rebase è
   meccanico.
2. **Il fix "watchdog sospensione/ripresa display" [4][5]** conferma che i
   crash Watchdog riguardano la piattaforma anche sul caso reale. Il nostro
   NOP del Watchdog in `services.jar` resta un work-around **QEMU-only**:
   non va portato su hardware (vedi TESTS.md).
3. **"Ritorno al firmware di fabbrica" su install firmware corrotta [4][5]**:
   il flusso update di GBOS può toccare componenti firmware board-level.
   **Mai eseguire updater/OTA GBOS sul ThinkBook**: gli update vanno testati
   solo in QEMU. Sul target usiamo solo boot passivo da USB.
4. **Lenovo Googlebook 15 rilasciato in Italia** (x86, "ruby"): eventuale
   secondo device di riferimento locale per confronti, ma il percorso ThinkBook
   resta mica/ARM64.
5. La matrice [1]-[5] conferma il catalogo a 5 device già derivato da
   `production_recovery.json` (lapis/mica/moonstone/quartz/ruby).
