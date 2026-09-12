// Feasibility gate, not a player, emulator, or general Linux runtime.
#include <errno.h>
#include <inttypes.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

extern uint64_t probe_x18_leaf(uint64_t);
extern uint64_t probe_x18_syscall(uint64_t);
extern uint64_t probe_x18_spin(uint64_t, uint64_t);

static int check_child(unsigned kind) {
    const uint64_t sentinel = UINT64_C(0x13579bdf2468ace0);
    uint64_t result;
    struct rlimit limit = {0, 0};
    if (setrlimit(RLIMIT_CORE, &limit) != 0) return 3;
    alarm(5);
    switch (kind) {
    case 0: result = probe_x18_leaf(sentinel); break;
    case 1: result = probe_x18_syscall(sentinel); break;
    default: result = probe_x18_spin(sentinel, UINT64_C(100000000)); break;
    }
    return result == sentinel ? 0 : 1;
}

int main(void) {
#if !defined(__APPLE__) || !defined(__aarch64__)
    fputs("This diagnostic requires Apple Silicon macOS.\n", stderr);
    return 2;
#endif
    const char *names[] = {"leaf", "darwin_syscall", "no_call_spin"};
    int failures = 0;
    puts("{\"probe\":\"direct_arm64_x18\",\"guest_instruction_writes\":0,\"cases\":[");
    for (unsigned kind = 0; kind < 3; kind++) {
        fflush(stdout);
        pid_t child = fork();
        if (child < 0) { perror("fork"); return 2; }
        if (child == 0) _exit(check_child(kind));
        int status;
        pid_t waited;
        do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
        if (waited < 0) { perror("waitpid"); return 2; }
        const char *outcome = "probe_error";
        if (WIFEXITED(status) && WEXITSTATUS(status) <= 1)
            outcome = WEXITSTATUS(status) == 0 ? "preserved" : "clobbered";
        if (WIFSIGNALED(status)) outcome = "signal";
        if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) failures++;
        printf("{\"case\":\"%s\",\"result\":\"%s\"}%s\n", names[kind], outcome, kind < 2 ? "," : "");
    }
    printf("],\"direct_execution_gate\":\"%s\"}\n", failures ? "blocked" : "not_disproved_not_certified");
    // A blocked route is a diagnostic result, not failure to run the test.
    return 0;
}
