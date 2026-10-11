#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-memory-refinement.XXXXXXXX")
printf 'Memory-refinement model artifacts: %s\n' "$run_root"
cd "$repo_root/Specs"
"${APALACHE_MC:-apalache-mc}" --out-dir="$run_root/typecheck" typecheck AriadneMemoryRefinement.tla > "$run_root/typecheck.log" 2>&1 || { cat "$run_root/typecheck.log"; exit 1; }
"${TLC:-tlc}" -workers 1 -metadir "$run_root/tlc" -config MemoryRefinement.cfg AriadneMemoryRefinement.tla > "$run_root/tlc.log" 2>&1 || { cat "$run_root/tlc.log"; exit 1; }
tail -8 "$run_root/tlc.log"
