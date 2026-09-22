#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d /tmp/ariadne-amd64-io.XXXXXX)"
trap 'rm -rf "$work"' EXIT

cd "$root"
python3 -m py_compile tools/check_amd64_io.py
python3 tools/check_amd64_io.py check
python3 tools/check_amd64_strings.py check

cd "$root/Specs"
apalache-mc typecheck --out-dir="$work/io-type" AMD64IOChecks.tla >"$work/io-type.log" 2>&1
apalache-mc typecheck --out-dir="$work/bind-type" AMD64IOStringsChecks.tla >"$work/bind-type.log" 2>&1
tlc -deadlock -cleanup -config AMD64IO.cfg AMD64IOChecks.tla >"$work/io-tlc.log" 2>&1
tlc -deadlock -cleanup -config AMD64IOStrings.cfg AMD64IOStringsChecks.tla >"$work/bind-tlc.log" 2>&1

cd "$root/lean"
lake build AMD64.IO AMD64.IOStrings
lake env lean AMD64/IO.lean
lake env lean AMD64/IOStrings.lean
lake env lean AMD64/IOAudit.lean

tail -n 8 "$work/io-type.log"
tail -n 8 "$work/bind-type.log"
tail -n 12 "$work/io-tlc.log"
tail -n 12 "$work/bind-tlc.log"
echo "AMD64 IO checks passed"
