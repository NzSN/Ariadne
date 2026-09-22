#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-amd64-integer.XXXXXXXX")
type_checker=${APALACHE_MC:-apalache-mc}
tlc_checker=${TLC:-tlc}
printf 'AMD64 integer artifacts: %s\n' "$run_root"

cd -- "$repo_root"
python3 -m json.tool Specs/AMD64/integer-coverage.json > /dev/null
python3 -m json.tool Specs/AMD64/integer-form-supplement.json > /dev/null

cd -- "$repo_root/lean"
lake build AMD64.IntegerSemantics AMD64.IntegerStateAdapter \
  AMD64.IntegerFormSupplement AMD64.IntegerExecution \
  AMD64.IntegerExecutionChecks 2>&1 | tee "$run_root/lean-build.log"
lake env lean AMD64/IntegerSemanticsChecks.lean 2>&1 | tee "$run_root/lean-checks.log"
lake env lean AMD64/IntegerStateAdapterChecks.lean 2>&1 | tee "$run_root/lean-state-adapter-checks.log"
lake env lean AMD64/IntegerAudit.lean 2>&1 | tee "$run_root/lean-axioms.log"
lake env lean AMD64/IntegerExecutionAudit.lean 2>&1 | tee "$run_root/lean-execution-axioms.log"

cd -- "$repo_root/Specs"
for module in AMD64IntegerCore AMD64IntegerArithmetic AMD64IntegerShiftBit \
              AMD64IntegerMulDiv AMD64IntegerChecks AMD64IntegerStateAdapter \
              AMD64IntegerStateAdapterChecks AMD64IntegerExecution \
              AMD64IntegerFormSupplement AMD64IntegerExecutionChecks; do
  "$type_checker" --out-dir="$run_root/typecheck-$module" typecheck "$module.tla" \
    2>&1 | tee "$run_root/typecheck-$module.log"
done

"$tlc_checker" -workers 2 -metadir "$run_root/tlc" \
  -config AMD64Integer.cfg AMD64IntegerChecks.tla \
  2>&1 | tee "$run_root/tlc.log"
"$tlc_checker" -workers 2 -metadir "$run_root/tlc-state-adapter" \
  -config AMD64IntegerStateAdapter.cfg AMD64IntegerStateAdapterChecks.tla \
  2>&1 | tee "$run_root/tlc-state-adapter.log"
"$tlc_checker" -workers 2 -metadir "$run_root/tlc-execution" \
  -config AMD64IntegerExecution.cfg AMD64IntegerExecutionChecks.tla \
  2>&1 | tee "$run_root/tlc-execution.log"

printf 'AMD64 integer pure kernels passed; instruction binding and listed coverage gaps remain open.\n'
