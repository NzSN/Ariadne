#!/usr/bin/env bash
set -euo pipefail

# G0/S1 checker. Run model tooling on the authorized remote WSL build host.
# APALACHE_MC/TLC select the qualification host's pinned launchers. Record tool
# versions and identities; optional explicit version pins reject tool drift.
# Do not silently choose one of the repository's historical toolchain records.
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-predicate-admission.XXXXXXXX")
apalache=${APALACHE_MC:-apalache-mc}
tlc=${TLC:-tlc}
apalache_pin=${APALACHE_VERSION_PIN:-}
tlc_pin=${TLC_VERSION_PIN:-}
printf 'Predicate-admission model artifacts: %s\n' "$run_root"

python3 "$repo_root/tests/bap/fixtures/guards/oracle.py" --check \
  > "$run_root/oracle.log" 2>&1 || { cat "$run_root/oracle.log"; exit 1; }
cat "$run_root/oracle.log"
python3 "$repo_root/tests/bap/fixtures/caller-coverage/oracle.py" --check \
  --output "$run_root/caller-coverage-oracle.json" \
  > "$run_root/caller-coverage-oracle.log" 2>&1 || {
    cat "$run_root/caller-coverage-oracle.log"; exit 1;
  }
cat "$run_root/caller-coverage-oracle.log"
python3 - "$repo_root" <<'PY'
import hashlib,json,pathlib,sys
base=pathlib.Path(sys.argv[1])/'tests/bap/fixtures/caller-coverage'
manifest=json.loads((base/'legacy-manifest.json').read_text())
for name,row in manifest['files'].items():
    if hashlib.sha256((base/'legacy-v2'/name).read_bytes()).hexdigest()!=row['sha256']:
        raise SystemExit('frozen legacy contract differs: '+name)
PY
sha256sum "$repo_root/Specs/AriadnePredicateAdmission.tla" \
  "$repo_root/Specs/check-predicate-admission.sh" \
  "$repo_root"/Specs/PredicateAdmission*.cfg \
  "$repo_root/tests/bap/fixtures/guards/oracle.py" \
  "$repo_root/tests/bap/fixtures/guards/contract.json" \
  "$repo_root/tests/bap/fixtures/caller-coverage/oracle.py" \
  "$repo_root/tests/bap/fixtures/caller-coverage/oracle-cases.json" \
  "$repo_root/tests/bap/fixtures/caller-coverage/raw-bap-observations.json" \
  "$repo_root/tests/bap/fixtures/caller-coverage/dump-four-shapes.json" \
  "$repo_root/tests/bap/fixtures/caller-coverage/legacy-manifest.json" \
  "$repo_root"/tests/bap/fixtures/caller-coverage/legacy-v2/* \
  > "$run_root/sources-before.sha256"

"$apalache" version > "$run_root/apalache-version.log" 2>&1
# The selected TLC launcher prints valid help with exit 1. Accept that status
# only with a positive version banner and help marker; unavailable launchers,
# crashes, empty output and a banner without help must still fail the probe.
tlc_help_status=0
"$tlc" -help > "$run_root/tlc-version.log" 2>&1 || tlc_help_status=$?
printf '%s\n' "$tlc_help_status" > "$run_root/tlc-help-status.txt"
if ! python3 - "$run_root/tlc-version.log" "$run_root/tlc-help-status.txt" <<'PY'
import pathlib
import re
import sys
path = pathlib.Path(sys.argv[1])
raw = path.read_text(errors="replace")
clean = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", raw)
path.with_name("tlc-version-clean.log").write_text(clean)
status = int(pathlib.Path(sys.argv[2]).read_text())
version = re.search(r"(?im)^\s*TLC2?\b[^\r\n]*\bVersion\s+[0-9][^\s]*", clean)
help_marker = re.search(r"(?im)^\s*(?:Usage\s*:|SYNOPSIS\b|-help\b)", clean)
sys.exit(0 if status in (0, 1) and version and help_marker else 1)
PY
then
  cat "$run_root/tlc-version.log"
  printf 'TLC help probe failed (exit %s or missing version/help identity).\n' "$tlc_help_status" >&2
  exit 1
fi
# Python is already required by the oracle; the minimal qualification rootfs
# need not install rg merely to inspect tool identities or completion messages.
contains_text() {
  python3 - "$1" "$2" <<'PY'
import pathlib
import sys
sys.exit(0 if sys.argv[1] in pathlib.Path(sys.argv[2]).read_text(errors="replace") else 1)
PY
}
if [[ -n $apalache_pin ]] && ! contains_text "$apalache_pin" "$run_root/apalache-version.log"; then
  cat "$run_root/apalache-version.log"
  printf 'Apalache does not match selected version pin %s\n' "$apalache_pin" >&2
  exit 1
fi
if [[ -n $tlc_pin ]] && ! contains_text "$tlc_pin" "$run_root/tlc-version-clean.log"; then
  cat "$run_root/tlc-version.log"
  printf 'TLC does not match selected version pin %s\n' "$tlc_pin" >&2
  exit 1
fi
sha256sum "$(command -v -- "$apalache")" "$(command -v -- "$tlc")" \
  > "$run_root/tool-launchers.sha256"
# Native jars can be recorded explicitly in addition to the launcher/version.
if [[ -n ${APALACHE_JAR:-} ]]; then
  sha256sum "$APALACHE_JAR" >> "$run_root/tool-launchers.sha256"
fi
if [[ -n ${TLC_JAR:-} ]]; then
  sha256sum "$TLC_JAR" >> "$run_root/tool-launchers.sha256"
fi

cd -- "$repo_root/Specs"
"$apalache" --out-dir="$run_root/typecheck" typecheck AriadnePredicateAdmission.tla \
  > "$run_root/typecheck.log" 2>&1 || { cat "$run_root/typecheck.log"; exit 1; }
count=0
for config_path in "$repo_root"/Specs/PredicateAdmission*.cfg; do
  config=$(basename -- "$config_path" .cfg)
  "$tlc" -workers 1 -metadir "$run_root/$config" -config "$config.cfg" \
    AriadnePredicateAdmission.tla > "$run_root/$config.log" 2>&1 || {
      cat "$run_root/$config.log"; exit 1;
    }
  contains_text 'Model checking completed. No error has been found.' "$run_root/$config.log" || {
    cat "$run_root/$config.log"; exit 1;
  }
  tail -8 "$run_root/$config.log"
  count=$((count+1))
done
sha256sum --check "$run_root/sources-before.sha256" > "$run_root/sources-stable.log"
printf 'Predicate admission: %s configurations passed safety and fair termination.\n' "$count"
