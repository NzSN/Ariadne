#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-amd64-shift.XXXXXXXX")
type_checker=${APALACHE_MC:-apalache-mc}
tlc_checker=${TLC:-tlc}

cd -- "$repo_root"
python3 -m json.tool Specs/AMD64/integer-shift-form-supplement.json >/dev/null

cd -- "$repo_root/lean"
lake build AMD64.IntegerShiftExecution AMD64.IntegerShiftExecutionChecks \
  2>&1 | tee "$run_root/lean-build.log"
lake env lean AMD64/IntegerShiftExecutionAudit.lean \
  2>&1 | tee "$run_root/lean-audit.log"

cd -- "$repo_root/Specs"
for module in AMD64IntegerShiftExecution AMD64IntegerShiftExecutionChecks; do
  "$type_checker" --out-dir="$run_root/typecheck-$module" typecheck "$module.tla" \
    2>&1 | tee "$run_root/typecheck-$module.log"
done

"$tlc_checker" -workers 2 -metadir "$run_root/tlc" \
  -config AMD64IntegerShiftExecution.cfg AMD64IntegerShiftExecutionChecks.tla \
  2>&1 | tee "$run_root/tlc.log"

printf 'AMD64 shift execution checkpoint passed: %s\n' "$run_root"
