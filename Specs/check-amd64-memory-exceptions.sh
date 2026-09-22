#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-amd64-memory.XXXXXXXX")
type_checker=${APALACHE_MC:-apalache-mc}
tlc_checker=${TLC:-tlc}

printf 'AMD64 memory/exception artifacts: %s\n' "$run_root"

cd -- "$repo_root/Specs"
for module in AMD64Memory AMD64Exceptions AMD64MemoryExceptionsChecks; do
  "$type_checker" --out-dir="$run_root/typecheck-$module" typecheck "$module.tla" \
    2>&1 | tee "$run_root/typecheck-$module.log"
done

"$tlc_checker" -workers 2 -metadir "$run_root/tlc" \
  -config AMD64MemoryExceptions.cfg AMD64MemoryExceptionsChecks.tla \
  2>&1 | tee "$run_root/tlc.log"

cd -- "$repo_root/lean"
lake build AMD64.Memory AMD64.Exceptions 2>&1 | tee "$run_root/lean-build.log"

if rg -n '\b(sorry|admit|axiom)\b' AMD64/Memory.lean AMD64/Exceptions.lean \
    >"$run_root/admission-scan.log"; then
  cat "$run_root/admission-scan.log"
  printf 'Unproved declaration found in memory/exception modules.\n' >&2
  exit 1
fi

printf 'AMD64 memory/exception foundation checks passed; full paging, delivery, and ordering remain open.\n'
