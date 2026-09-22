#!/usr/bin/env bash
set -euo pipefail

# A foundation gate, deliberately NOT the full-ISA completion gate. The PDF
# inventory check is offline unless AMD64_MANUAL_CACHE requests hash verification.
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-amd64-foundation.XXXXXXXX")
type_checker=${APALACHE_MC:-apalache-mc}
tlc_checker=${TLC:-tlc}
printf 'AMD64 foundation artifacts: %s\n' "$run_root"
cd -- "$repo_root"

inventory_args=()
if [[ -n ${AMD64_MANUAL_CACHE:-} ]]; then
  inventory_args+=(--cache "$AMD64_MANUAL_CACHE")
fi
python3 tools/amd64_inventory.py check "${inventory_args[@]}" 2>&1 | tee "$run_root/inventory.log"
python3 -m unittest discover -s tools -p 'test_amd64_inventory.py' 2>&1 | tee "$run_root/inventory-tests.log"
python3 -m unittest discover -s tools -p 'test_amd64_acceptance.py' 2>&1 | tee "$run_root/acceptance-tests.log"
python3 - <<'PY'
import hashlib
import json
from pathlib import Path
lock = json.loads(Path('Specs/AMD64/correspondence.lock.json').read_text())
for entry in lock['files']:
    actual = hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()
    if actual != entry['sha256']:
        raise SystemExit(f"Correspondence source changed; review mapping before repinning: {entry['path']}")
print('Register-view transcription source hashes match the reviewed lock.')
PY

cd -- "$repo_root/lean"
lake build 2>&1 | tee "$run_root/lean-build.log"
lake env lean Audit.lean 2>&1 | tee "$run_root/lean-axioms.log"

cd -- "$repo_root/Specs"
for module in AMD64RegisterViews AMD64RegisterViewsChecks AMD64RegisterViewsSymbolic; do
  "$type_checker" --out-dir="$run_root/typecheck-$module" typecheck "$module.tla" \
    2>&1 | tee "$run_root/typecheck-$module.log"
done
"$tlc_checker" -workers 2 -metadir "$run_root/tlc" \
  -config AMD64RegisterViews.cfg AMD64RegisterViewsChecks.tla \
  2>&1 | tee "$run_root/tlc.log"
"$type_checker" --out-dir="$run_root/symbolic" check \
  --init=Init --next=Next --inv=Safety --length=1 --no-deadlock AMD64RegisterViewsSymbolic.tla \
  2>&1 | tee "$run_root/symbolic.log"

printf 'AMD64 source inventory and register-view foundation passed; full ISA coverage remains pending.\n'
