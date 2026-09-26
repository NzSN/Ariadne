#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
decoder="$repo_root/target/ariadne-llvm-mc"
bash "$repo_root/native/llvm_mc/build.sh" "$decoder"
ARIADNE_LLVM_MC="$decoder" cargo test --offline --manifest-path "$repo_root/Cargo.toml" \
  --test llvm_mc -- --ignored

ARIADNE_LLVM_MC="$decoder" cargo test --offline --manifest-path "$repo_root/Cargo.toml" \
  --test effects -- --ignored
