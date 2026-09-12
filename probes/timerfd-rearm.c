/* Owned Linux ABI fixture: rearming discards unread old expirations. */
#include "linux-syscall.h"

struct timespec { long sec, nsec; };
struct itimerspec { struct timespec interval, value; };
struct epoll_event { unsigned int events, pad; unsigned long data; };

static int arm(int fd, int clock, int absolute, long nanoseconds)
{
    struct itimerspec timer = {0};
    if (absolute && syscall6(113, clock, (long) &timer.value, 0, 0, 0, 0))
        return 1;
    timer.value.nsec += nanoseconds;
    timer.value.sec += timer.value.nsec / 1000000000;
    timer.value.nsec %= 1000000000;
    return syscall6(86, fd, absolute, (long) &timer, 0, 0, 0) != 0;
}

static int rearm_case(int clock, int absolute)
{
    long timer = syscall6(85, clock, 0x800, 0, 0, 0, 0);
    long epoll = syscall6(20, 0, 0, 0, 0, 0, 0);
    if (timer < 0 || epoll < 0)
        return 1;
    struct epoll_event event = {1, 0, 123};
    if (syscall6(21, epoll, 1, timer, (long) &event, 0, 0))
        return 2;
    for (int repeat = 0; repeat < 8; repeat++) {
        if (arm(timer, clock, absolute, 1000000))
            return 3;
        if (syscall6(22, epoll, (long) &event, 1, 1000, 0, 0) != 1)
            return 4;
        /* Deliberately do not read: timerfd_settime resets the old counter. */
        if (arm(timer, clock, absolute, 100000000))
            return 5;
        if (syscall6(22, epoll, (long) &event, 1, 0, 0, 0) != 0)
            return 6;
        unsigned long ticks = 0;
        if (syscall6(63, timer, (long) &ticks, 8, 0, 0, 0) != -11)
            return 7;
        if (syscall6(22, epoll, (long) &event, 1, 1000, 0, 0) != 1)
            return 8;
        if (event.data != 123 || event.events != 1 ||
            syscall6(63, timer, (long) &ticks, 8, 0, 0, 0) != 8 || ticks != 1)
            return 9;
    }
    syscall6(57, timer, 0, 0, 0, 0, 0);
    syscall6(57, epoll, 0, 0, 0, 0, 0);
    return 0;
}

__attribute__((noreturn)) void _start(void)
{
    long status = 0;
    for (int clock = 0; clock < 2 && !status; clock++)
        for (int absolute = 0; absolute < 2 && !status; absolute++)
            status = rearm_case(clock, absolute);
    if (!status) {
        static const char message[] = "PASS: timerfd rearm clears unread readiness (32 cycles, both clocks/modes)\n";
        syscall6(64, 1, (long) message, sizeof(message) - 1, 0, 0, 0);
    }
    syscall6(94, status, 0, 0, 0, 0, 0);
    __builtin_unreachable();
}
