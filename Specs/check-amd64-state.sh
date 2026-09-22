#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d /tmp/ariadne-amd64-state.XXXXXX)"
trap 'rm -rf "$work"' EXIT

cd "$root"
python3 -m py_compile tools/check_amd64_state.py
python3 tools/check_amd64_state.py check

cd "$root/Specs"
apalache-mc typecheck --out-dir="$work/apalache" AMD64ArchitecturalStateChecks.tla \
  >"$work/apalache.log" 2>&1
tlc -deadlock -cleanup -config AMD64ArchitecturalState.cfg \
  AMD64ArchitecturalStateChecks.tla >"$work/tlc.log" 2>&1

cd "$root/lean"
lake env lean AMD64/ArchitecturalState.lean
lake build
lake env lean Audit.lean

tail -n 8 "$work/apalache.log"
tail -n 12 "$work/tlc.log"
echo "AMD64 architectural-state checks passed"
