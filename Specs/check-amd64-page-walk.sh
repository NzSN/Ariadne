#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-amd64-pagewalk.XXXXXXXX")
type_checker=${APALACHE_MC:-apalache-mc}
tlc_checker=${TLC:-tlc}

printf 'AMD64 page-walk artifacts: %s\n' "$run_root"

cd -- "$repo_root/Specs"
for module in AMD64PageWalk AMD64PageWalkChecks; do
  "$type_checker" --out-dir="$run_root/typecheck-$module" typecheck "$module.tla" \
    2>&1 | tee "$run_root/typecheck-$module.log"
done

"$tlc_checker" -workers 2 -metadir "$run_root/tlc" \
  -config AMD64PageWalk.cfg AMD64PageWalkChecks.tla \
  2>&1 | tee "$run_root/tlc.log"

cd -- "$repo_root/lean"
lake build AMD64.PageWalk 2>&1 | tee "$run_root/lean-build.log"

if rg -n '\b(sorry|admit|axiom)\b' AMD64/PageWalk.lean \
    >"$run_root/admission-scan.log"; then
  cat "$run_root/admission-scan.log"
  printf 'Unproved declaration found in page-walk module.\n' >&2
  exit 1
fi

printf 'AMD64 page-walk common certificates passed; variant-specific closure remains open.\n'
