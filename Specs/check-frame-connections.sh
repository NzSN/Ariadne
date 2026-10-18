#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=${FRAME_CONNECTION_MODEL_OUT:-$repo_root/target/frame-connections-model/check}
mkdir -p "$run_root"
sha256sum "$repo_root/Specs/AriadneFrameConnections.tla" "$repo_root/Specs/check-frame-connections.sh" "$repo_root"/Specs/FrameConnections*.cfg > "$run_root/sources.sha256"
python3 "$repo_root/tests/investigation/fixtures/frame_connections_oracle.py" --check > "$run_root/oracle.log"
cd -- "$repo_root/Specs"
"${APALACHE_MC:-apalache-mc}" --out-dir="$run_root/typecheck" typecheck AriadneFrameConnections.tla > "$run_root/typecheck.log" 2>&1
for config in FrameConnections*.cfg; do
    name=${config%.cfg}
    "${TLC:-tlc}" -workers 1 -metadir "$run_root/$name" -config "$config" AriadneFrameConnections.tla > "$run_root/$name.log" 2>&1
    rg -q 'Model checking completed. No error has been found.' "$run_root/$name.log"
done
sha256sum --check "$run_root/sources.sha256" > "$run_root/sources-stable.log"
printf 'Frame connections: all finite configurations and independent oracle passed. Artifacts: %s\n' "$run_root"
