#!/bin/bash
set -euo pipefail
runtime_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
task_audio_root="$(<"$runtime_root/state/audio.path")"
test -S "$task_audio_root/native"
task_linker="$(rustc --print sysroot)/lib/rustlib/aarch64-apple-darwin/bin/gcc-ld/ld.lld"
xcrun clang --target=aarch64-linux-gnu -c "$runtime_root/probes/libc-start.S" -o "$runtime_root/build/libc-start.o"
xcrun clang --target=aarch64-linux-gnu -O1 -ffreestanding -fno-stack-protector \
  -Wall -Wextra -Werror -c "$runtime_root/probes/audio-library.c" -o "$runtime_root/build/audio-library.o"
"$task_linker" -e _start -z max-page-size=65536 --dynamic-linker /lib/ld-linux-aarch64.so.1 \
  "$runtime_root/build/libc-start.o" "$runtime_root/build/audio-library.o" \
  "$runtime_root/build/sysroot/usr/lib/aarch64-linux-gnu/libc.so.6" \
  -o "$runtime_root/build/audio-library.elf"
"$runtime_root/vendor/elfuse/build/elfuse" --no-rosetta --clear-env \
  --timeout 10 --env "PULSE_COOKIE=$task_audio_root/cookie" \
  --env "PULSE_SERVER=unix:$task_audio_root/native" \
  --sysroot "$runtime_root/build/sysroot" -- "$runtime_root/build/audio-library.elf"
