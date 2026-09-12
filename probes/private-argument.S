// This fixture validates a public test value, never an actual credential.
.text
.global _start
_start:
    ldr x0, [sp]
    cmp x0, #2
    b.ne failed
    ldr x1, [sp, #16]
    adr x2, expected
compare:
    ldrb w3, [x1], #1
    ldrb w4, [x2], #1
    cmp w3, w4
    b.ne failed
    cbnz w3, compare
    mov x0, #0
    b done
failed:
    mov x0, #1
done:
    mov x8, #94
    svc #0
.section .rodata
expected:
    .asciz "public-fixture-value"
