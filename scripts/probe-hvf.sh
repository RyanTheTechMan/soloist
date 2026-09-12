#!/bin/bash
set -euo pipefail
runtime_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
elfuse="$runtime_root/vendor/elfuse/build/elfuse"
task_linker="$(rustc --print sysroot)/lib/rustlib/aarch64-apple-darwin/bin/gcc-ld/ld.lld"
test -x "$elfuse"
test -x "$task_linker"
mkdir -p "$runtime_root/build"
xcrun clang --target=aarch64-linux-gnu -c "$runtime_root/probes/linux-arm64.S" \
  -o "$runtime_root/build/linux-arm64.o"
"$task_linker" -e _start -z max-page-size=65536 \
  "$runtime_root/build/linux-arm64.o" -o "$runtime_root/build/linux-arm64.elf"
"$elfuse" --no-rosetta --clear-env -- "$runtime_root/build/linux-arm64.elf"
xcrun clang --target=aarch64-linux-gnu -O1 -ffreestanding -fno-stack-protector \
  -Wall -Wextra -Werror -c "$runtime_root/probes/proc-readlink.c" \
  -o "$runtime_root/build/proc-readlink.o"
"$task_linker" -e _start -z max-page-size=65536 \
  "$runtime_root/build/proc-readlink.o" -o "$runtime_root/build/proc-readlink.elf"
"$elfuse" --no-rosetta --clear-env -- "$runtime_root/build/proc-readlink.elf"
xcrun clang --target=aarch64-linux-gnu -c "$runtime_root/probes/private-argument.S" \
  -o "$runtime_root/build/private-argument.o"
"$task_linker" -e _start -z max-page-size=65536 \
  "$runtime_root/build/private-argument.o" -o "$runtime_root/build/private-argument.elf"
python3 "$runtime_root/scripts/test-private-argument.py"
xcrun clang --target=aarch64-linux-gnu -O1 -ffreestanding -fno-stack-protector \
  -Wall -Wextra -Werror -c "$runtime_root/probes/futex-clocks.c" \
  -o "$runtime_root/build/futex-clocks.o"
"$task_linker" -e _start -z max-page-size=65536 \
  "$runtime_root/build/futex-clocks.o" -o "$runtime_root/build/futex-clocks.elf"
"$elfuse" --no-rosetta --clear-env --timeout 5 -- "$runtime_root/build/futex-clocks.elf"
xcrun clang --target=aarch64-linux-gnu -O1 -ffreestanding -fno-stack-protector \
  -Wall -Wextra -Werror -c "$runtime_root/probes/multicast.c" \
  -o "$runtime_root/build/multicast.o"
"$task_linker" -e _start -z max-page-size=65536 \
  "$runtime_root/build/multicast.o" -o "$runtime_root/build/multicast.elf"
"$elfuse" --no-rosetta --clear-env --timeout 5 -- "$runtime_root/build/multicast.elf"
xcrun clang --target=aarch64-linux-gnu -O1 -ffreestanding -fno-stack-protector \
  -Wall -Wextra -Werror -c "$runtime_root/probes/timerfd-rearm.c" \
  -o "$runtime_root/build/timerfd-rearm.o"
"$task_linker" -e _start -z max-page-size=65536 \
  "$runtime_root/build/timerfd-rearm.o" -o "$runtime_root/build/timerfd-rearm.elf"
"$elfuse" --no-rosetta --clear-env --timeout 10 -- "$runtime_root/build/timerfd-rearm.elf"
xcrun clang --target=aarch64-linux-gnu -O1 -ffreestanding -fno-stack-protector \
  -Wall -Wextra -Werror -c "$runtime_root/probes/epoll-rearm.c" \
  -o "$runtime_root/build/epoll-rearm.o"
"$task_linker" -e _start -z max-page-size=65536 \
  "$runtime_root/build/epoll-rearm.o" -o "$runtime_root/build/epoll-rearm.elf"
"$elfuse" --no-rosetta --clear-env --timeout 5 -- "$runtime_root/build/epoll-rearm.elf"
