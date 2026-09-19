#!/usr/bin/env bash
set -euo pipefail

# Execute real 32/64-bit semantic vectors and the finite stateflow compositions.
# TLC and APALACHE_MC may select checker executables. No generated files enter
# the repo; preserve this printed directory when sharing verification evidence.
spec_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
tlc_checker=${TLC:-tlc}
type_checker=${APALACHE_MC:-apalache-mc}
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-x86-64.XXXXXXXX")
printf 'x86-64 check artifacts: %s\n' "$run_root"
cd -- "$spec_dir"

for module in AriadneX86_64Semantics AriadneX86_64SemanticsChecks AriadneX86_64SemanticsExample; do
  "$type_checker" --out-dir="$run_root/typecheck-$module" typecheck "$module.tla" \
    2>&1 | tee "$run_root/typecheck-$module.log"
done
"$tlc_checker" -workers 2 -metadir "$run_root/semantics" \
  -config X86_64Semantics.cfg AriadneX86_64SemanticsChecks.tla \
  2>&1 | tee "$run_root/semantics.log"
for mode in Stateflow Unsupported MissingState MissingEdge; do
  "$tlc_checker" -workers 2 -metadir "$run_root/$mode" \
    -config "X86_64$mode.cfg" AriadneX86_64SemanticsExample.tla \
    2>&1 | tee "$run_root/$mode.log"
done
printf 'x86-64 typing, semantic vectors, and four stateflow checks passed.\n'
