#!/usr/bin/env bash
set -euo pipefail
# All model-tool execution belongs on the authorized remote WSL host.
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-alignment-hypotheses.XXXXXXXX")
apalache=${APALACHE_MC:-apalache-mc}
tlc=${TLC:-tlc}
printf 'Alignment-hypothesis model artifacts: %s\n' "$run_root"
sha256sum "$repo_root/Specs/AriadneAlignmentHypothesis.tla" \
  "$repo_root/Specs/check-alignment-hypotheses.sh" "$repo_root"/Specs/AlignmentHypothesis*.cfg \
  "$repo_root/tests/bap/fixtures/alignment-hypotheses/oracle.py" \
  "$repo_root/tests/bap/fixtures/alignment-hypotheses/contract.json" \
  > "$run_root/sources-before.sha256"
python3 "$repo_root/tests/bap/fixtures/alignment-hypotheses/oracle.py" --check \
  --output "$run_root/oracle-result.json" > "$run_root/oracle.log" 2>&1 || {
    cat "$run_root/oracle.log"; exit 1;
  }
cat "$run_root/oracle.log"
"$apalache" version > "$run_root/apalache-version.log" 2>&1
tlc_status=0
"$tlc" -help > "$run_root/tlc-version.log" 2>&1 || tlc_status=$?
python3 - "$run_root/tlc-version.log" "$tlc_status" <<'PY'
from pathlib import Path
import re
import sys
text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", Path(sys.argv[1]).read_text(errors="replace"))
version = re.search(r"(?im)^\s*TLC2?\b[^\r\n]*\bVersion\s+[0-9][^\s]*", text)
help_marker = re.search(r"(?im)^\s*(?:Usage\s*:|SYNOPSIS\b|-help\b)", text)
if int(sys.argv[2]) not in (0, 1) or not version or not help_marker:
    raise SystemExit("TLC launcher did not return valid help/version identity")
PY
python3 - "$run_root" "${APALACHE_VERSION_PIN:-}" "${TLC_VERSION_PIN:-}" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
for pin, name in zip(sys.argv[2:], ("apalache", "tlc")):
    if pin and pin not in (root / f"{name}-version.log").read_text():
        raise SystemExit(f"{name} version differs from selected pin {pin}")
PY
sha256sum "$(command -v -- "$apalache")" "$(command -v -- "$tlc")" > "$run_root/tool-launchers.sha256"
if [[ -n ${APALACHE_JAR:-} ]]; then sha256sum "$APALACHE_JAR" >> "$run_root/tool-launchers.sha256"; fi
if [[ -n ${TLC_JAR:-} ]]; then sha256sum "$TLC_JAR" >> "$run_root/tool-launchers.sha256"; fi
cd -- "$repo_root/Specs"
"$apalache" --out-dir="$run_root/typecheck" typecheck AriadneAlignmentHypothesis.tla \
  > "$run_root/typecheck.log" 2>&1 || { cat "$run_root/typecheck.log"; exit 1; }
count=0
for config_path in "$repo_root"/Specs/AlignmentHypothesis*.cfg; do
  config=$(basename -- "$config_path" .cfg)
  "$tlc" -workers 1 -metadir "$run_root/$config" -config "$config.cfg" \
    AriadneAlignmentHypothesis.tla > "$run_root/$config.log" 2>&1 || {
      cat "$run_root/$config.log"; exit 1;
    }
  python3 - "$run_root/$config.log" <<'PY'
from pathlib import Path
import sys
if "Model checking completed. No error has been found." not in Path(sys.argv[1]).read_text():
    raise SystemExit("TLC did not report successful completion")
PY
  tail -8 "$run_root/$config.log"
  count=$((count+1))
done
sha256sum --check "$run_root/sources-before.sha256" > "$run_root/sources-stable.log"
printf 'Alignment hypotheses: %s configurations passed safety, scenario outcomes and fair termination.\n' "$count"
