// Owned diagnostic code, compiled normally: no ELF patching or injected code.
// Deliberately exercises Linux's use of x18 in a disposable child process.
// Never calls a host library with the experimental x18 value installed.
.text
.p2align 2
.globl _probe_x18_leaf
_probe_x18_leaf:
    mov x9, x18
    mov x18, x0
    mov x0, x18
    mov x18, x9
    ret

.globl _probe_x18_syscall
_probe_x18_syscall:
    stp x19, x30, [sp, #-16]!
    mov x19, x18
    mov x18, x0
    // Darwin getpid, not a Linux syscall or a syscall-number substitution.
    mov x16, #20
    svc #0x80
    mov x0, x18
    mov x18, x19
    ldp x19, x30, [sp], #16
    ret

.globl _probe_x18_spin
_probe_x18_spin:
    mov x9, x18
    mov x18, x0
    // No calls or explicit exceptions: observe asynchronous interruption too.
1:
    subs x1, x1, #1
    b.ne 1b
    mov x0, x18
    mov x18, x9
    ret
