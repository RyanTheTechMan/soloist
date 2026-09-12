// Standard Linux AArch64 process entry for owned libc-linked fixtures.
.text
.global _start
_start:
    mov x5, x0
    ldr x1, [sp]
    add x2, sp, #8
    adr x0, main
    mov x3, #0
    mov x4, #0
    mov x6, sp
    bl __libc_start_main
    brk #0
.section .note.GNU-stack,"",@progbits
