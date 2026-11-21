/* probe: init statico minimo per il test di bring-up GBOS su ThinkBook.
 * Scrive su /dev/sda2 (FAT, label BOOTLOG): modello DT, CPU, partizioni, dmesg.
 * Poi reboot per rileggere il log da Windows. */
#define _GNU_SOURCE
#include <dirent.h>
#include <fcntl.h>
#include <linux/reboot.h>
#include <sys/klog.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int logfd = -1;

static void wlog(const char *s) {
    if (logfd >= 0) { write(logfd, s, strlen(s)); fsync(logfd); }
}

static void dumpfile(const char *path, const char *title) {
    char buf[16384];
    int fd = open(path, O_RDONLY);
    if (fd < 0) { wlog(title); wlog(" (non disponibile)\n"); return; }
    wlog("\n===== "); wlog(title); wlog(" =====\n");
    ssize_t n;
    while ((n = read(fd, buf, sizeof(buf))) > 0) write(logfd, buf, n);
    close(fd);
}

static void dump_pstore(void) {
    mkdir("/sys/fs/pstore", 0755);
    if (mount("pstore", "/sys/fs/pstore", "pstore", 0, NULL) != 0) {
        wlog("\n(pstore non disponibile)\n");
        return;
    }
    DIR *d = opendir("/sys/fs/pstore");
    if (!d) { wlog("\n(pstore opendir fallito)\n"); return; }
    struct dirent *e;
    while ((e = readdir(d))) {
        if (e->d_name[0] == '.') continue;
        char path[300];
        snprintf(path, sizeof(path), "/sys/fs/pstore/%s", e->d_name);
        dumpfile(path, e->d_name);
    }
    closedir(d);
}

int main(void) {
    mkdir("/proc", 0755); mkdir("/sys", 0755); mkdir("/dev", 0755); mkdir("/tmp", 0755);
    mount("proc", "/proc", "proc", 0, NULL);
    mount("sysfs", "/sys", "sysfs", 0, NULL);
    mount("devtmpfs", "/dev", "devtmpfs", 0, NULL);

    /* attende che il kernel registri sda2 (scan SCSI/USB + parsing MBR):
     * senza devtmpfs serve polling su /proc/partitions, NON stat sul nodo
     * (il nodo creato con mknod renderebbe sempre vero lo stat) */
    int sda2_ok = 0;
    for (int i = 0; i < 60; i++) {
        char pbuf[8192];
        int pf = open("/proc/partitions", O_RDONLY);
        ssize_t pn = (pf >= 0) ? read(pf, pbuf, sizeof(pbuf) - 1) : -1;
        if (pf >= 0) close(pf);
        if (pn > 0) {
            pbuf[pn] = 0;
            if (strstr(pbuf, " sda2\n") || strstr(pbuf, " sda2\t")) { sda2_ok = 1; break; }
        }
        mknod("/dev/sda2", S_IFBLK | 0600, makedev(8, 2));
        usleep(500000);
    }

    logfd = open("/tmp/log.tmp", O_CREAT | O_WRONLY | O_TRUNC, 0644);

    wlog("=== GBOS bring-up probe (mica kernel su ThinkBook) ===\n");
    {
        char msg[64];
        snprintf(msg, sizeof(msg), "sda2 registrato dal kernel: %s\n",
                 sda2_ok ? "SI" : "NO (timeout 30s)");
        wlog(msg);
    }
    dumpfile("/sys/firmware/devicetree/base/model", "DT model");
    dumpfile("/sys/firmware/devicetree/base/compatible", "DT compatible");
    dumpfile("/proc/cpuinfo", "cpuinfo");
    dumpfile("/proc/partitions", "partitions");
    dumpfile("/proc/meminfo", "meminfo (prime righe nel buffer)");
    dump_pstore();

    char *dmesg = malloc(4 << 20);
    if (dmesg) {
        long n = klogctl(3, dmesg, 4 << 20); /* READ_ALL */
        if (n > 0) {
            wlog("\n===== dmesg =====\n");
            write(logfd, dmesg, n);
        }
        free(dmesg);
    }
    fsync(logfd); close(logfd);

    /* copia su FAT: monta /dev/sda2 e trasferisce il file */
    mkdir("/log", 0755);
    int mounted = mount("/dev/sda2", "/log", "vfat", 0, NULL) == 0;
    if (!mounted) {
        /* fallback: prova direttamente su ext4 nel caso il log sia ext4 */
        mounted = mount("/dev/sda2", "/log", "ext4", 0, NULL) == 0;
    }
    if (!mounted) {
        char mmsg[64];
        int mf = open("/tmp/mount.err", O_CREAT | O_WRONLY | O_TRUNC, 0644);
        if (mf >= 0) { write(mf, "mount fallito\n", 13); close(mf); }
    } else {
        char buf[65536];
        int in = open("/tmp/log.tmp", O_RDONLY);
        int out = open("/log/gbos-probe.log", O_CREAT | O_WRONLY | O_TRUNC, 0644);
        if (in >= 0 && out >= 0) {
            ssize_t n;
            while ((n = read(in, buf, sizeof(buf))) > 0) write(out, buf, n);
            fsync(out);
        }
    }
    sync();
    reboot(LINUX_REBOOT_CMD_POWER_OFF);
    for (;;) pause();
}
