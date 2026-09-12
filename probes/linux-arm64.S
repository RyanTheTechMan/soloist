// An owned Linux ARM64 ELF. The runtime must not rewrite any instructions.
.text
.global _start
_start:
    mov x18, #0xace0
    movk x18, #0x2468, lsl #16
    movk x18, #0x9bdf, lsl #32
    movk x18, #0x1357, lsl #48
    mov x19, x18
    // Linux getpid: x18 must survive a real syscall boundary.
    mov x8, #172
    svc #0
    cmp x18, x19
    b.ne failed
    // Thread pointer is Linux guest state, never Darwin's host TLS.
    msr tpidr_el0, x19
    mrs x20, tpidr_el0
    cmp x20, x19
    b.ne failed
    mov x21, #0xe100
    movk x21, #0x5f5, lsl #16
spin:
    subs x21, x21, #1
    b.ne spin
    cmp x18, x19
    b.ne failed
    mrs x20, tpidr_el0
    cmp x20, x19
    b.ne failed
    mov x0, #1
    adr x1, message
    mov x2, #message_end-message
    mov x8, #64
    svc #0
    cmp x0, #message_end-message
    b.ne failed
    mov x0, #0
    b done
failed:
    mov x0, #1
done:
    mov x8, #94
    svc #0
.section .rodata
message:
    .ascii "PASS: unchanged Linux ARM64 x18, TLS, syscall and loop\n"
message_end:
