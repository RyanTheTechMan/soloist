#!/bin/bash
set -euo pipefail
runtime_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
elfuse_root="$runtime_root/vendor/elfuse"
mkdir -p "$runtime_root/build"
xcrun clang -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined \
  -I"$elfuse_root/src" "$runtime_root/probes/text-integrity-test.c" \
  "$elfuse_root/src/core/text-integrity.c" -o "$runtime_root/build/text-integrity-test"
"$runtime_root/build/text-integrity-test"
bash "$runtime_root/scripts/probe-hvf.sh"
python3 "$runtime_root/scripts/verify-startup.py"
