/* Owned fixture: EPOLL_CTL_MOD rechecks an already-readable edge trigger. */
#include "linux-syscall.h"
struct epoll_event { unsigned int events, pad; unsigned long data; };

__attribute__((noreturn)) void _start(void)
{
    long status = 0;
    long fd = syscall6(19, 1, 0x800, 0, 0, 0, 0);
    long epoll = syscall6(20, 0, 0, 0, 0, 0, 0);
    struct epoll_event registration = {0x80000001U, 0, 123}, event = {0};
    if (fd < 0 || epoll < 0 ||
        syscall6(21, epoll, 1, fd, (long) &registration, 0, 0))
        status = 1;
    for (int repeat = 0; repeat < 32 && !status; repeat++) {
        if (syscall6(22, epoll, (long) &event, 1, 20, 0, 0) != 1 ||
            event.events != 1 || event.data != registration.data)
            status = 2;
        if (!status && syscall6(22, epoll, (long) &event, 1, 0, 0, 0) != 0)
            status = 3;
        registration.data++;
        /* Asio leaves its interrupter readable and wakes it by MOD alone. */
        if (!status && syscall6(21, epoll, 3, fd, (long) &registration, 0, 0))
            status = 4;
    }
    if (!status) {
        static const char message[] = "PASS: edge-triggered epoll MOD rechecks unread eventfd (32 cycles)\n";
        syscall6(64, 1, (long) message, sizeof(message) - 1, 0, 0, 0);
    }
    syscall6(94, status, 0, 0, 0, 0, 0);
    __builtin_unreachable();
}
