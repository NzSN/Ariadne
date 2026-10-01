#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
runtime=${BAP_RUNTIME_ROOT:-"$repo_root/tmp/bap-setup/stable"}
output=${1:-"$repo_root/target/ariadne-bap-lift"}
python3 "$repo_root/native/bap/setup.py" --check --runtime "$runtime"
mkdir -p -- "$(dirname -- "$output")"
g++ -std=c++17 -O2 -Wall -Wextra -Werror -Wno-unused-parameter \
  -I"$runtime/usr/local/include" "$repo_root/native/bap/lift.cpp" \
  "$runtime/usr/local/lib/libbap.so.2.5.0" \
  -Wl,-rpath-link,"$runtime/usr/lib/x86_64-linux-gnu" -o "$output"
LD_LIBRARY_PATH="$runtime/usr/local/lib:$runtime/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" "$output" --version
