/* Owned freestanding Linux AArch64 regression fixture; no libc required. */
static long syscall4(long nr, long a, long b, long c, long d)
{
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    register long x8 __asm__("x8") = nr;
    __asm__ volatile("svc #0" : "+r"(x0) : "r"(x1), "r"(x2), "r"(x3),
                     "r"(x8) : "memory", "cc");
    return x0;
}

static long link(const char *path, char *buf, long size)
{
    return syscall4(78, -100, (long) path, (long) buf, size);
}

__attribute__((noreturn)) void _start(void)
{
    char buf[4096];
    char pidpath[64] = "/proc/";
    long status = 1;
    if (link("/proc", buf, sizeof(buf)) != -22)
        goto done;
    if (link("/proc/", buf, sizeof(buf)) != -22)
        goto done;
    long len = link("/proc/self", buf, sizeof(buf));
    if (len <= 0 || len > 20)
        goto done;
    long pid = 0;
    for (long i = 0; i < len; i++) {
        if (buf[i] < '0' || buf[i] > '9')
            goto done;
        pid = pid * 10 + buf[i] - '0';
        pidpath[6 + i] = buf[i];
    }
    pidpath[6 + len] = 0;
    if (pid != syscall4(172, 0, 0, 0, 0))
        goto done;
    if (link(pidpath, buf, sizeof(buf)) != -22)
        goto done;
    if (link("/proc/self/", buf, sizeof(buf)) != -22)
        goto done;
    if (link("/proc/self/status", buf, sizeof(buf)) != -22)
        goto done;
    if (link("/proc/nonexistent-fixture-entry", buf, sizeof(buf)) != -2)
        goto done;
    if (link("/proc/self/exe", buf, sizeof(buf)) <= 0 || buf[0] != '/')
        goto done;
    if (link("/proc/self/exe", buf, 1) != 1 || buf[0] != '/')
        goto done;
    status = 0;
    static const char msg[] = "PASS: Linux procfs readlink semantics\n";
    syscall4(64, 1, (long) msg, sizeof(msg) - 1, 0);
done:
    syscall4(94, status, 0, 0, 0);
    __builtin_unreachable();
}
