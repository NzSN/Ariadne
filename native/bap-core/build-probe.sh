#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
runtime=${BAP_RUNTIME_ROOT:-"$root/tmp/bap-setup/stable"}
output=${1:-"$root/target/bap-core-a0/ariadne-bap-core-probe"}
python3 "$root/native/bap/setup.py" --check --runtime "$runtime"
mkdir -p -- "$(dirname -- "$output")"
g++ -std=c++17 -O2 -Wall -Wextra -Werror -Wno-unused-parameter \
  -I"$runtime/usr/local/include" "$root/native/bap-core/probe.cpp" \
  "$runtime/usr/local/lib/libbap.so.2.5.0" \
  -Wl,-rpath-link,"$runtime/usr/lib/x86_64-linux-gnu" -o "$output"
