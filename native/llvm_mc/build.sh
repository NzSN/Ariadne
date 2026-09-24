#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
include_dir=${LLVM20_INCLUDE_DIR:-/usr/include/llvm-20}
c_include_dir=${LLVM20_C_INCLUDE_DIR:-"$(dirname -- "$include_dir")/llvm-c-20"}
library=${LLVM20_LIBRARY:-/usr/lib/x86_64-linux-gnu/libLLVM.so.20.1}
output=${1:-"$repo_root/target/ariadne-llvm-mc"}

if [[ ! -f "$include_dir/llvm/Config/llvm-config.h" ||
      ! -f "$c_include_dir/llvm-c/DataTypes.h" || ! -f "$library" ]]; then
  printf 'LLVM 20.1.2 headers or library unavailable; set LLVM20_INCLUDE_DIR and LLVM20_LIBRARY\n' >&2
  exit 2
fi

mkdir -p -- "$(dirname -- "$output")"
g++ -std=c++17 -O2 -Wall -Wextra -Werror -Wno-unused-parameter \
  -I"$include_dir" -I"$c_include_dir" \
  "$repo_root/native/llvm_mc/decode.cpp" "$library" -o "$output"
"$output" --version
