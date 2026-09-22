#!/usr/bin/env bash
set -euo pipefail

# Discover all expansion modules rather than silently checking only the original
# register-view foundation. Full coverage is a separate, optional final gate;
# passing module checks alone does not certify instruction/state completeness.
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-amd64-suite.XXXXXXXX")
type_checker=${APALACHE_MC:-apalache-mc}
tlc_checker=${TLC:-tlc}
require_complete=false
require_milestone=""
case ${1:-} in
  "") ;;
  --require-complete) require_complete=true ;;
  --require-milestone)
    [[ $# -eq 2 ]] || { printf 'A milestone name is required.\n' >&2; exit 2; }
    require_milestone=$2 ;;
  *) printf 'Usage: bash Specs/check-amd64.sh [--require-milestone NAME | --require-complete]\n' >&2; exit 2 ;;
esac
printf 'AMD64 suite artifacts: %s\n' "$run_root"
cd -- "$repo_root"
python3 - "$run_root/source-snapshot.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
paths = set(Path('Specs').glob('*.tla')) | set(Path('Specs').glob('AMD64*.cfg'))
paths |= set(Path('lean').rglob('*.lean')) - set(Path('lean/.lake').rglob('*.lean'))
paths |= set(Path('tools').glob('*amd64*.py'))
paths |= set(Path('Specs').glob('check-amd64*.sh'))
paths |= set(Path('Specs/AMD64').glob('*.json'))
paths |= {Path('lean/lean-toolchain'), Path('lean/lakefile.toml')}
snapshot = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}
Path(sys.argv[1]).write_text(json.dumps(snapshot, indent=2) + '\n')
PY
python3 tools/amd64_inventory.py check 2>&1 | tee "$run_root/inventory.log"
python3 tools/amd64_forms.py check 2>&1 | tee "$run_root/forms.log"
python3 tools/check_amd64_state.py check 2>&1 | tee "$run_root/state-inventory.log"
python3 tools/check_amd64_strings.py check 2>&1 | tee "$run_root/string-inventory.log"
python3 tools/check_amd64_io.py check 2>&1 | tee "$run_root/io-inventory.log"
python3 tools/amd64_profile.py check 2>&1 | tee "$run_root/profile-coverage.log"
python3 -m unittest discover -s tools -p 'test_amd64_*.py' 2>&1 | tee "$run_root/python-tests.log"

cd -- "$repo_root/lean"
mapfile -t lean_sources < <(rg --files AMD64 -g '*.lean' | sort)
lean_modules=()
for source in "${lean_sources[@]}"; do
  module=${source%.lean}
  lean_modules+=("${module//\//.}")
done
lake build AMD64 "${lean_modules[@]}" 2>&1 | tee "$run_root/lean-build.log"
# Audit every discovered module even before a new module reaches the public
# root import list. Missing imports must not create an unchecked proof island.
printf 'import %s\n' "${lean_modules[@]}" > "$run_root/AuditAll.lean"
cat Audit.lean >> "$run_root/AuditAll.lean"
lake env lean "$run_root/AuditAll.lean" 2>&1 | tee "$run_root/lean-audit.log"

cd -- "$repo_root/Specs"
python3 - "$type_checker" "$run_root" <<'PY'
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import subprocess
import sys

checker, directory = sys.argv[1:]
jobs = int(os.environ.get('AMD64_TYPECHECK_JOBS', '2'))
if jobs < 1:
    raise SystemExit('AMD64_TYPECHECK_JOBS must be positive')

def check(source):
    module = source.stem
    log = Path(directory) / f'typecheck-{module}.log'
    with log.open('w') as output:
        result = subprocess.run(
            [checker, f'--out-dir={directory}/typecheck-{module}', 'typecheck', str(source)],
            stdout=output, stderr=subprocess.STDOUT)
    return module, result.returncode, log

failed = []
with ThreadPoolExecutor(max_workers=jobs) as pool:
    futures = [pool.submit(check, source) for source in sorted(Path('.').glob('AMD64*.tla'))]
    for future in as_completed(futures):
        module, code, log = future.result()
        print(f'Typecheck {module}: {"PASS" if code == 0 else "FAIL"}; {log}', flush=True)
        if code:
            failed.append(module)
            print(log.read_text()[-6000:], flush=True)
if failed:
    raise SystemExit('Typecheck failures: ' + ', '.join(failed))
PY
for config in AMD64*.cfg; do
  base=${config%.cfg}
  module="${base}Checks.tla"
  if [[ ! -f $module ]]; then
    printf 'Missing explicit Checks module for configuration %s\n' "$config" >&2
    exit 1
  fi
  "$tlc_checker" -workers 2 -metadir "$run_root/tlc-$base" -config "$config" "$module" \
    2>&1 | tee "$run_root/tlc-$base.log"
done
for source in AMD64*Symbolic.tla; do
  [[ -f $source ]] || continue
  module=${source%.tla}
  "$type_checker" --out-dir="$run_root/symbolic-$module" check \
    --init=Init --next=Next --inv=Safety --length=1 --no-deadlock "$source" \
    2>&1 | tee "$run_root/symbolic-$module.log"
done
cd -- "$repo_root"
python3 - "$run_root/source-snapshot.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
snapshot = json.loads(Path(sys.argv[1]).read_text())
paths = set(Path('Specs').glob('*.tla')) | set(Path('Specs').glob('AMD64*.cfg'))
paths |= set(Path('lean').rglob('*.lean')) - set(Path('lean/.lake').rglob('*.lean'))
paths |= set(Path('tools').glob('*amd64*.py')) | set(Path('Specs').glob('check-amd64*.sh'))
paths |= set(Path('Specs/AMD64').glob('*.json'))
paths |= {Path('lean/lean-toolchain'), Path('lean/lakefile.toml')}
added = {str(path) for path in paths} - snapshot.keys()
changed = [name for name, digest in snapshot.items()
           if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest]
if changed or added:
    raise SystemExit('Checked sources changed during the suite; no stable acceptance: ' + ', '.join(sorted(set(changed) | added)))
print('Checked source hashes stayed stable throughout the suite.')
PY
if [[ -n $require_milestone ]]; then
  python3 tools/amd64_profile.py check --require-milestone "$require_milestone" \
    2>&1 | tee "$run_root/milestone.log"
elif "$require_complete"; then
  python3 tools/amd64_inventory.py check --require-complete 2>&1 | tee "$run_root/completeness.log"
else
  printf 'AMD64 component checks passed. Profile milestone acceptance is separate; full-manual coverage remains a roadmap target.\n'
fi
