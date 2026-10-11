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
"$checker" --out-dir="$run_root/LLVMIR" check \
  --init=Init --next=Next --inv=Safety --length=8 --no-deadlock AriadneLLVMIRExample.tla
"$checker" --out-dir="$run_root/MachineState" check \
  --init=Init --next=Next --inv=Safety --length=6 --no-deadlock AriadneMachineStateExample.tla
for scenario in Input InputLimit; do
  "$checker" --out-dir="$run_root/$scenario" check \
    --config="$scenario.cfg" --init=Init --next=Next --inv=Safety \
    --length=6 --no-deadlock AriadneInputChecks.tla
done
"$checker" --out-dir="$run_root/Effects" check \
  --init=Init --next=Next --inv=Safety --length=1 --no-deadlock AriadneEffectsChecks.tla
for module in AriadneMemoryRefinement AriadneZeroBaseOffset; do
  "$checker" --out-dir="$run_root/$module-safety" check \
    --init=Init --next=Next --inv=Safety --length=1 --no-deadlock "$module.tla"
done
for scenario in FramePaths FramePathsComplete FramePathsCountOne FramePathsScanLimit FramePathsZeroVisits FramePathsExternalStop; do
  "$checker" --out-dir="$run_root/$scenario" check \
    --config="$scenario.cfg" --init=Init --next=Next --inv=Safety \
    --length=32 --no-deadlock AriadneFramePaths.tla
done
printf 'Core scenarios/calls through %s; pipeline/IR through 8; stateflow/input through 6; effects/decisions through 1; six frame-path scenarios through 32.\n' "$bound"
