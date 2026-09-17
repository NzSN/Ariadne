#!/usr/bin/env bash
set -euo pipefail

# Usage: bash Specs/check-apalache.sh [bound] [Binary|Dump|Loop|Closed|all]
# APALACHE_MC can select a specific executable. Artifacts stay outside the repo.
spec_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
checker=${APALACHE_MC:-apalache-mc}
bound=${1:-6}
scenario=${2:-all}
if [[ ! $bound =~ ^[0-9]+$ ]]; then
  printf 'Bound must be a nonnegative integer.\n' >&2
  exit 2
fi
case "$scenario" in
  all) scenarios=(Binary Dump Loop Closed) ;;
  Binary|Dump|Loop|Closed) scenarios=("$scenario") ;;
  *) printf 'Unknown scenario: %s\n' "$scenario" >&2; exit 2 ;;
esac

run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-apalache.XXXXXXXX")
printf 'Apalache artifacts: %s\n' "$run_root"
cd -- "$spec_dir"
"$checker" version
# Discover every specification so a new module cannot silently skip typing.
for source in "$spec_dir"/*.tla; do
  module=$(basename -- "$source" .tla)
  "$checker" --out-dir="$run_root/typecheck-$module" typecheck "$source"
done
for name in "${scenarios[@]}"; do
  "$checker" --out-dir="$run_root/$name" check \
    --cinit="${name}Constants" --init=Init --next=Next --inv=Safety \
    --length="$bound" --no-deadlock AriadneExample.tla
done
"$checker" --out-dir="$run_root/Pipeline" check \
  --init=Init --next=Next --inv=Safety --length=8 --no-deadlock AriadnePipeline.tla
"$checker" --out-dir="$run_root/Calls" check \
  --init=Init --next=Next --inv=Safety --length="$bound" --no-deadlock AriadneCalls.tla
printf 'Scenario and call-policy safety checks passed through bound %s; pipeline through 8.\n' "$bound"
