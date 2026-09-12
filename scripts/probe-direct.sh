#!/bin/bash
set -euo pipefail
runtime_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "Requires Apple Silicon macOS" >&2
  exit 2
fi
mkdir -p "$runtime_root/build"
xcrun clang -std=c11 -O2 -Wall -Wextra -Werror \
  "$runtime_root/probes/direct_arm64.c" "$runtime_root/probes/direct_arm64.S" \
  -o "$runtime_root/build/direct-arm64-probe"
"$runtime_root/build/direct-arm64-probe"
