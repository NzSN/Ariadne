#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-frame-paths.XXXXXXXX")
cd "$repo_root/Specs"
"${TLC:-tlc}" -workers 1 -metadir "$run_root/tlc" -config FramePaths.cfg AriadneFramePaths.tla > "$run_root/tlc.log" 2>&1 || { cat "$run_root/tlc.log"; exit 1; }
tail -8 "$run_root/tlc.log"
