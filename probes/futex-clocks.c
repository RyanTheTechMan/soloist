/* Own Linux ABI fixture, no account, network, libc or guest code patches. */
#include "linux-syscall.h"
struct timespec { long sec, nsec; };
static int word;

static long now(int clock, struct timespec *ts)
{
    return syscall6(113, clock, (long) ts, 0, 0, 0, 0);
}

static int wait_case(int clock, int flags)
{
    struct timespec start, end, deadline;
    if (now(1, &start) || now(clock, &deadline))
        return 1;
    deadline.nsec += 100000000;
    if (deadline.nsec >= 1000000000) {
        deadline.sec++;
        deadline.nsec -= 1000000000;
    }
    long rc = syscall6(98, (long) &word, 9 | flags, 0, (long) &deadline, 0, -1);
    if (now(1, &end) || rc != -110)
        return 1;
    long elapsed = (end.sec - start.sec) * 1000000000 + end.nsec - start.nsec;
    return elapsed < 80000000 || elapsed > 2000000000;
}

__attribute__((noreturn)) void _start(void)
{
    long status = wait_case(1, 0x80) || wait_case(0, 0x180);
    struct timespec bad = {-1, 0};
    if (syscall6(98, (long) &word, 0x89, 0, (long) &bad, 0, -1) != -22)
        status = 1;
    if (!status) {
        static const char msg[] = "PASS: futex monotonic/realtime absolute waits and invalid timeout\n";
        syscall6(64, 1, (long) msg, sizeof(msg) - 1, 0, 0, 0);
    }
    syscall6(94, status, 0, 0, 0, 0, 0);
    __builtin_unreachable();
}
