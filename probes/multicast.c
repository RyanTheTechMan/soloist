/* Own socket-option fixture; joins/leaves a group without sending packets. */
#include "linux-syscall.h"

static int error_queue_case(int domain, int level, int option)
{
    long fd = syscall6(198, domain, 2, 0, 0, 0, 0);
    if (fd < 0)
        return 1;
    int status = 0;
    for (int flag = 0; flag <= 1; flag++) {
        int actual = -1;
        unsigned int size = 4;
        if (syscall6(208, fd, level, option, (long) &flag, 4, 0) ||
            syscall6(209, fd, level, option, (long) &actual, (long) &size, 0) ||
            actual != flag || size != 4)
            status = 1;
    }
    unsigned char msg[56] = {0};
    if (syscall6(212, fd, (long) msg, 0x2000, 0, 0, 0) != -11)
        status = 1;
    if (syscall6(207, fd, (long) msg, sizeof(msg), 0x2000, 0, 0) != -11)
        status = 1;
    syscall6(57, fd, 0, 0, 0, 0, 0);
    return status;
}

__attribute__((noreturn)) void _start(void)
{
    long status = 1;
    long fd = syscall6(198, 2, 2, 0, 0, 0, 0);
    if (fd >= 0) {
        unsigned char membership[8] = {224, 0, 0, 251, 0, 0, 0, 0};
        long added = syscall6(208, fd, 0, 35, (long) membership, 8, 0);
        long dropped = syscall6(208, fd, 0, 36, (long) membership, 8, 0);
        status = added != 0 || dropped != 0;
        unsigned char ttl = 255;
        int loop = 1, actual = 0;
        unsigned int size = 4;
        if (syscall6(208, fd, 0, 33, (long) &ttl, 1, 0) ||
            syscall6(208, fd, 0, 34, (long) &loop, 4, 0) ||
            syscall6(209, fd, 0, 33, (long) &actual, (long) &size, 0) ||
            actual != 255 || size != 4)
            status = 1;
        size = 1;
        actual = 0;
        if (syscall6(209, fd, 0, 34, (long) &actual, (long) &size, 0) ||
            actual != 1 || size != 1)
            status = 1;
        actual = 256;
        if (syscall6(208, fd, 0, 33, (long) &actual, 4, 0) != -22)
            status = 1;
        syscall6(57, fd, 0, 0, 0, 0, 0);
    }
    if (error_queue_case(2, 0, 11) || error_queue_case(10, 41, 25))
        status = 1;
    if (!status) {
        static const char msg[] = "PASS: Linux multicast options and IPv4/IPv6 empty error queues\n";
        syscall6(64, 1, (long) msg, sizeof(msg) - 1, 0, 0, 0);
    }
    syscall6(94, status, 0, 0, 0, 0, 0);
    __builtin_unreachable();
}
