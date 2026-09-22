#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d /tmp/ariadne-amd64-strings.XXXXXX)"
trap 'rm -rf "$work"' EXIT

cd "$root"
python3 -m py_compile tools/check_amd64_strings.py
python3 tools/check_amd64_strings.py check

cd "$root/Specs"
apalache-mc typecheck --out-dir="$work/apalache" AMD64StringsChecks.tla \
  >"$work/apalache.log" 2>&1
apalache-mc typecheck --out-dir="$work/apalache-memory" AMD64StringsMemoryChecks.tla \
  >"$work/apalache-memory.log" 2>&1
tlc -deadlock -cleanup -config AMD64Strings.cfg AMD64StringsChecks.tla \
  >"$work/tlc.log" 2>&1
tlc -deadlock -cleanup -config AMD64StringsMemory.cfg AMD64StringsMemoryChecks.tla \
  >"$work/tlc-memory.log" 2>&1

cd "$root/lean"
lake build AMD64.ArchitecturalState AMD64.Memory AMD64.Exceptions \
  AMD64.IntegerSemantics AMD64.IntegerStateAdapter
lake env lean AMD64/Strings.lean
lake build AMD64.Strings
lake env lean AMD64/StringsAudit.lean
lake env lean AMD64/StringsMemory.lean
lake build AMD64.StringsMemory
lake env lean AMD64/StringsMemoryAudit.lean

tail -n 8 "$work/apalache.log"
tail -n 8 "$work/apalache-memory.log"
tail -n 12 "$work/tlc.log"
tail -n 12 "$work/tlc-memory.log"
echo "AMD64 string/repetition checks passed"
