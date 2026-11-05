// vm-egltest.c — sonda EGL nel guest: ripercorre la catena display -> ANGLE
// -> vulkan (SwiftShader) e logga ogni passo su logcat (che scorre sulla
// console seriale). Oneshot al boot, prima che surfaceflinger crashi.
#include <dlfcn.h>
#include <android/log.h>
#include <string.h>

#define LOGI(...) __android_log_print(4, "vm-egltest", __VA_ARGS__)
#define LOGE(...) __android_log_print(6, "vm-egltest", __VA_ARGS__)

typedef void *EGLDisplay_;
typedef unsigned int EGLBoolean_;
typedef int EGLint_;
typedef void *EGLConfig_;
typedef void *EGLContext_;
typedef void *EGLSurface_;

int main(void) {
    LOGI("=== START egltest");

    void *h = dlopen("libEGL.so", RTLD_NOW | RTLD_GLOBAL);
    if (!h) { LOGE("dlopen libEGL.so: %s", dlerror()); return 1; }

    void *(*eglGetDisplay_)(void *) =
        (void *(*)(void *))dlsym(h, "eglGetDisplay");
    EGLBoolean_ (*eglInitialize_)(EGLDisplay_, EGLint_ *, EGLint_ *) =
        dlsym(h, "eglInitialize");
    const char *(*eglQueryString_)(EGLDisplay_, EGLint_) =
        dlsym(h, "eglQueryString");
    EGLBoolean_ (*eglChooseConfig_)(EGLDisplay_, const EGLint_ *, EGLConfig_ *,
                                    EGLint_, EGLint_ *) = dlsym(h, "eglChooseConfig");
    EGLint_ (*eglGetError_)(void) = dlsym(h, "eglGetError");
    if (!eglGetDisplay_ || !eglInitialize_ || !eglQueryString_ ||
        !eglChooseConfig_ || !eglGetError_) {
        LOGE("dlsym EGL fallito: %s", dlerror());
        return 1;
    }

    EGLDisplay_ dpy = eglGetDisplay_((void *)0 /*EGL_DEFAULT_DISPLAY*/);
    LOGI("eglGetDisplay(EGL_DEFAULT_DISPLAY) = %p", dpy);
    if (!dpy || dpy == (void *)0) { LOGE("nessun display"); return 2; }

    EGLint_ maj = 0, mi = 0;
    EGLBoolean_ ok = eglInitialize_(dpy, &maj, &mi);
    LOGI("eglInitialize = %d  versione %d.%d  eglError=0x%x", (int)ok, maj, mi,
         ok ? 0 : eglGetError_());
    if (!ok) { LOGE("=== FAIL eglInitialize (ANGLE/vulkan probabilmente)"); return 3; }

    const char *ven = eglQueryString_(dpy, 0x3053 /*EGL_VENDOR*/);
    const char *ver = eglQueryString_(dpy, 0x3054 /*EGL_VERSION*/);
    const char *api = eglQueryString_(dpy, 0x308D /*EGL_CLIENT_APIS*/);
    const char *ext = eglQueryString_(dpy, 0x3055 /*EGL_EXTENSIONS*/);
    LOGI("EGL_VENDOR = %s", ven ? ven : "(null)");
    LOGI("EGL_VERSION = %s", ver ? ver : "(null)");
    LOGI("EGL_CLIENT_APIS = %s", api ? api : "(null)");
    if (ext) {
        // logga gli ext in blocchi per non traboccare il buffer logcat
        char buf[380];
        const char *p = ext;
        while (*p) {
            size_t n = strlen(p) < 370 ? strlen(p) : 370;
            memcpy(buf, p, n); buf[n] = 0;
            LOGI("EXT| %s", buf);
            p += n;
        }
    }

    EGLConfig_ cfg = 0; EGLint_ ncfg = 0;
    const EGLint_ attrs[] = {
        0x3024 /*RED*/, 8, 0x3023 /*GREEN*/, 8, 0x3022 /*BLUE*/, 8,
        0x3021 /*ALPHA*/, 8, 0x3025 /*DEPTH*/, 0, 0x3026 /*STENCIL*/, 0,
        0x3041 /*SURFACE_TYPE*/, 0x0004 /*WINDOW*/ | 0x0008 /*PBUFFER*/,
        0x3040 /*RENDERABLE_TYPE*/, 0x0004 /*GLES2*/,
        0x3038 /*NONE*/ };
    ok = eglChooseConfig_(dpy, attrs, &cfg, 1, &ncfg);
    LOGI("eglChooseConfig = %d  nconfig=%d  eglError=0x%x", (int)ok, ncfg,
         ok ? 0 : eglGetError_());
    if (!ok || ncfg < 1) LOGE("=== FAIL eglChooseConfig (il vecchio 'no suitable EGLConfig')");

    LOGI("=== DONE egltest");
    return 0;
}
