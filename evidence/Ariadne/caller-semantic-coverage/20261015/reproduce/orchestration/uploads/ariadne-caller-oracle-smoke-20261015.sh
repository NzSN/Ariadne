#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
  external=/mnt/d/ariadne-caller-coverage-20261015
  cp /mnt/d/ariadne-caller-oracle-smoke-20261015.sh "$external/diag-oracle.sh"
  cp /mnt/d/ariadne-caller-oracle-sources-20261015.tar.gz "$external/diag-oracle-input.tar.gz"
  chown jlc:jlc "$external/diag-oracle.sh" "$external/diag-oracle-input.tar.gz"
  exec runuser -u jlc -- bash "$external/run.sh" bash /caller-work/diag-oracle.sh --inside
fi
scratch=$(mktemp -d /caller-work/tmp/caller-oracle.XXXXXXXX)
mkdir "$scratch/repo"
tar -xzf /caller-work/diag-oracle-input.tar.gz -C "$scratch/repo"
cd "$scratch/repo"
sha256sum tests/bap/fixtures/caller-coverage/oracle.py tests/bap/fixtures/caller-coverage/oracle-cases.json
status=0
python3 tests/bap/fixtures/caller-coverage/oracle.py --check --output "$scratch/result.json" > "$scratch/oracle.log" 2>&1 || status=$?
cat "$scratch/oracle.log"
printf 'Oracle scratch artifacts: %s\n' "$scratch"
exit "$status"
