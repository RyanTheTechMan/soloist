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
python3 "$runtime_root/scripts/test-pi-mutex.py"
python3 "$runtime_root/scripts/test-host-termination.py"
python3 "$runtime_root/scripts/test-lifecycle.py"
python3 "$runtime_root/scripts/test-receiver.py"
python3 "$runtime_root/scripts/test-client-api.py"
python3 "$runtime_root/scripts/test-playback-cycles.py"
python3 "$runtime_root/scripts/verify-startup.py"
