#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-frame-paths.XXXXXXXX")
printf 'Frame-path model artifacts: %s\n' "$run_root"
cd "$repo_root/Specs"
"${APALACHE_MC:-apalache-mc}" --out-dir="$run_root/typecheck" typecheck AriadneFramePaths.tla > "$run_root/typecheck.log" 2>&1 || { cat "$run_root/typecheck.log"; exit 1; }
for config in FramePaths FramePathsComplete FramePathsCountOne FramePathsScanLimit FramePathsZeroVisits FramePathsExternalStop; do
  "${TLC:-tlc}" -workers 1 -metadir "$run_root/$config" -config "$config.cfg" AriadneFramePaths.tla > "$run_root/$config.log" 2>&1 || { cat "$run_root/$config.log"; exit 1; }
  tail -8 "$run_root/$config.log"
done
