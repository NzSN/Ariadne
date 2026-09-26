#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-effects.XXXXXXXX")
printf 'Effects check artifacts: %s\n' "$run_root"
cd "$repo_root/Specs"
for module in AriadneEffects AriadneEffectsChecks; do
  "${APALACHE_MC:-apalache-mc}" --out-dir="$run_root/$module" typecheck "$module.tla" > "$run_root/$module.log" 2>&1 || { cat "$run_root/$module.log"; exit 1; }
done
"${TLC:-tlc}" -workers 1 -metadir "$run_root/tlc" -config Effects.cfg AriadneEffectsChecks.tla 2>&1 | tee "$run_root/tlc.log"
