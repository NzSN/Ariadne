#!/usr/bin/env bash
set -euo pipefail

# Usage: bash Specs/check-apalache.sh [bound] [Binary|Dump|Loop|Closed|all]
# APALACHE_MC can select a specific executable. Artifacts stay outside the repo.
spec_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
checker=${APALACHE_MC:-apalache-mc}
memory_checker=${MEMORY_APALACHE_MC:-$checker}
tlc=${TLC:-tlc}
memory_tlc=${MEMORY_TLC:-$tlc}
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
# Algebraic definitions stay authoritative; derive a fresh finite solver copy.
python3 "$spec_dir/../tools/generate_memory_solver.py" --specs "$spec_dir" --output "$run_root/memory-lookup"
for directory in solver controls; do
  for source in "$run_root/memory-lookup/$directory"/*.tla; do
    module=$(basename -- "$source" .tla)
    (cd "$run_root/memory-lookup/$directory" && "$memory_checker" \
      --out-dir="$run_root/memory-type-$directory-$module" typecheck "$source")
  done
done
for scenario in Pointwise Whole; do
  (cd "$run_root/memory-lookup/controls" && "$memory_tlc" -workers 1 \
    -metadir "$run_root/memory-$scenario-tlc" -config "FiniteLookup$scenario.cfg" \
    FiniteLookupEquality.tla) > "$run_root/memory-$scenario-tlc.log" 2>&1 || { cat "$run_root/memory-$scenario-tlc.log"; exit 1; }
  tail -8 "$run_root/memory-$scenario-tlc.log"
done
for name in static all-pairs; do
  if [[ $name == static ]]; then
    module=MemoryPairPartitionCoverage
    config=MemoryPairPartitionCoverage
  else
    module=MemoryPairPartitionChecks
    config=MemoryPairPartitionChecks-cover
  fi
  (cd "$run_root/memory-lookup/solver" && "$memory_tlc" -workers 1 \
    -metadir "$run_root/memory-$name-cover-tlc" -config "$config.cfg" "$module.tla") \
    > "$run_root/memory-$name-cover-tlc.log" 2>&1 || { cat "$run_root/memory-$name-cover-tlc.log"; exit 1; }
  tail -8 "$run_root/memory-$name-cover-tlc.log"
done
(cd "$run_root/memory-lookup/authority" && "$memory_tlc" -workers 1 \
  -metadir "$run_root/memory-authority-tlc" -config MemoryRefinement.cfg \
  AriadneMemoryRefinement.tla) > "$run_root/memory-authority-tlc.log" 2>&1 || { cat "$run_root/memory-authority-tlc.log"; exit 1; }
tail -8 "$run_root/memory-authority-tlc.log"
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
# Original Memory Safety = IdealSafety /\ RepresentationSafety /\ CandidateSafety.
# The twenty complete original fact-class/transfer-kind domains cover every
# original pair; no sampled or narrower domain is credited. Full Safety TLC
# remains unchanged in check-memory-refinement.sh.
for invariant in IdealSafety CandidateSafety; do
  "$checker" --out-dir="$run_root/AriadneMemoryRefinement-$invariant" check \
    --init=Init --next=Next --inv="$invariant" --length=1 --no-deadlock AriadneMemoryRefinement.tla
done
for fact in Exact Plain Composed Unknown; do
  for kind in Copy Add Sub And Constant; do
    (cd "$run_root/memory-lookup/solver" && "$memory_checker" \
      --out-dir="$run_root/MemoryPair$fact$kind" check \
      --config="MemoryPair$fact$kind.cfg" --init="PairInit$fact$kind" --next=PairNext \
      --inv=PairRepresentationSafety --length=1 --no-deadlock MemoryPairPartitionChecks.tla)
  done
done
"$checker" --out-dir="$run_root/AriadneZeroBaseOffset-safety" check \
  --init=Init --next=Next --inv=Safety --length=1 --no-deadlock AriadneZeroBaseOffset.tla
for scenario in FramePaths FramePathsComplete FramePathsCountOne FramePathsScanLimit FramePathsZeroVisits FramePathsExternalStop; do
  "$checker" --out-dir="$run_root/$scenario" check \
    --config="$scenario.cfg" --init=Init --next=Next --inv=Safety \
    --length=32 --no-deadlock AriadneFramePaths.tla
done
printf 'Core scenarios/calls through %s; pipeline/IR through 8; stateflow/input through 6; effects/decisions through 1; six frame-path scenarios through 32.\n' "$bound"
