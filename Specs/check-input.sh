#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-input-model.XXXXXXXX")
printf 'Input model artifacts: %s\n' "$run_root"
cd "$repo_root/Specs"
for module in AriadneInput AriadneInputChecks; do
  "${APALACHE_MC:-apalache-mc}" --out-dir="$run_root/$module" typecheck "$module.tla" > "$run_root/$module.log" 2>&1 || { cat "$run_root/$module.log"; exit 1; }
done
for config in Input InputLimit; do
  "${TLC:-tlc}" -workers 1 -metadir "$run_root/$config" -config "$config.cfg" AriadneInputChecks.tla > "$run_root/$config.log" 2>&1 || { cat "$run_root/$config.log"; exit 1; }
  tail -8 "$run_root/$config.log"
done
