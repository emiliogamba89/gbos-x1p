#!/usr/bin/env bash
# stub libandroid.so + sync_wait per il namespace sphal:
# - vulkan.swiftshader.so dichiara DT_NEEDED libandroid.so ma sphal non puo'
#   caricare le NDK app libs di sistema -> dlopen falliva
# - sync_wait (mangled _Z9sync_waitii, GLOBAL UND) vive in libsync.so piattaforma
#   che non e' nei NEEDED del ICD e non e' raggiungibile in sphal
# Le AHardwareBuffer_* (tranne createFromHandle) risolvono da libnativewindow.
set -eu
cd /mnt/c/Users/emili/Desktop/gbos-x1p/tools/qemu_bench
cat > /tmp/libandroid_stub.c << 'EOF'
/* AHardwareBuffer_createFromHandle non raggiungibile nel VM: NULL ->
   SwiftShader salta l'import via handle (usa i path fd/AHB pointer). */
void *AHardwareBuffer_createFromHandle(void *desc, void *handle, int format) {
    (void)desc; (void)handle; (void)format;
    return 0;
}

/* __android_log_write: no-op (liblog non raggiungibile in sphal) */
int __android_log_write(int prio, const char *tag, const char *text) {
    (void)prio; (void)tag; (void)text;
    return 1;
}

/* sync_wait(int fd, int timeout): semantica libsync per fence fd sync_file:
   poll(POLLIN); 0 se segnalato, -1 con ETIMEDOUT al timeout, -1 su errore.
   Esportato col nome mangled C++ usato da SwiftShader. */
#include <poll.h>
#include <errno.h>
int _Z9sync_waitii(int fd, int timeout) {
    struct pollfd p;
    int ret;
    p.fd = fd;
    p.events = 0x0001 /*POLLIN*/;
    p.revents = 0;
    do {
        ret = poll(&p, 1, timeout);
    } while (ret < 0 && errno == 4 /*EINTR*/);
    if (ret < 0) return -1;
    if (ret == 0) { errno = 110 /*ETIMEDOUT*/; return -1; }
    return 0;
}
EOF
~/tc/w-clang -shared -fPIC -O2 -Wl,-soname,libandroid.so -o /tmp/libandroid.so /tmp/libandroid_stub.c
cp /tmp/libandroid.so ../../downloads/cuttlefish/extract/swiftshader/libandroid.so
~/clang-arm64/clang-r584948b/bin/llvm-readelf --dyn-syms /tmp/libandroid.so | grep -E "_Z9sync_waitii|createFromHandle"
echo "[OK] stub aggiornato"
