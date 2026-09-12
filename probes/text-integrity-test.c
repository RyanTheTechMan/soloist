/* Test the actual elfuse verifier with non-executable fixture data only. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "core/text-integrity.h"

static unsigned char fixture[8192];
int guest_read(const guest_t *g, uint64_t address, void *out, size_t count)
{
    (void) g;
    if (address > sizeof(fixture) || count > sizeof(fixture) - address)
        return -1;
    memcpy(out, fixture + address, count);
    return 0;
}

int main(void)
{
    char path[] = "/tmp/soloist-text-test-XXXXXX";
    int fd = mkstemp(path);
    assert(fd >= 0);
    for (size_t i = 0; i < 5000; i++) fixture[i] = (unsigned char) (i * 13);
    assert(write(fd, fixture, 5000) == 5000);
    assert(close(fd) == 0);
    elf_info_t info = {0};
    info.num_segments = 1;
    info.segments[0] = (elf_segment_t) {.filesz = 5000, .memsz = 5100, .flags = PF_R | PF_X};
    text_integrity_t check = {0};
    assert(text_integrity_add(&check, &info, 0, path));
    assert(text_integrity_verify(&check, NULL));
    fixture[4096] ^= 1;
    assert(!text_integrity_verify(&check, NULL));
    fixture[4096] ^= 1;
    fixture[5010] = 1;
    assert(!text_integrity_verify(&check, NULL));
    fixture[5010] = 0;
    assert(text_integrity_verify(&check, NULL));
    check.segments[0].address = sizeof(fixture);
    assert(!text_integrity_verify(&check, NULL));
    text_integrity_destroy(&check);
    assert(!text_integrity_verify(&check, NULL));
    info.has_text_relocations = true;
    assert(!text_integrity_add(&check, &info, 0, path));
    info.has_text_relocations = false;
    info.segments[0].flags |= PF_W;
    assert(!text_integrity_add(&check, &info, 0, path));
    info.segments[0].flags = PF_R | PF_X;
    info.segments[0].filesz = 6000;
    assert(!text_integrity_add(&check, &info, 0, path));
    info.segments[0].memsz = 6000;
    assert(!text_integrity_add(&check, &info, 0, path));
    info.segments[0].filesz = 5000;
    info.segments[0].gpa = UINT64_MAX;
    assert(!text_integrity_add(&check, &info, 1, path));
    text_integrity_destroy(&check);
    assert(unlink(path) == 0);
    puts("PASS: integrity detects differences, BSS changes, unreadable memory, RWX, truncation and overflow");
    return 0;
}
