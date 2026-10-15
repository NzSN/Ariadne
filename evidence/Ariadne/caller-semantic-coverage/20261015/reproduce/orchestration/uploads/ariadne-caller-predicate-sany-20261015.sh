#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
  external=/mnt/d/ariadne-caller-coverage-20261015
  cp /mnt/d/ariadne-caller-predicate-sany-20261015.sh "$external/diag-sany.sh"
  cp /mnt/d/ariadne-caller-predicate-model-fixed-20261015.tla "$external/diag-model.tla"
  chown jlc:jlc "$external/diag-sany.sh"
  chown jlc:jlc "$external/diag-model.tla"
  exec runuser -u jlc -- bash "$external/run.sh" bash /caller-work/diag-sany.sh --inside
fi
meta=$(mktemp -d /caller-work/tmp/predicate-sany.XXXXXXXX)
cp /caller-work/diag-model.tla "$meta/AriadnePredicateAdmission.tla"
cp /home/nzsn/Repos/Ariadne-caller-coverage-20261015/Specs/PredicateAdmissionAligned.cfg "$meta/PredicateAdmissionAligned.cfg"
cd "$meta"
sha256sum AriadnePredicateAdmission.tla
status=0
"${TLC:-tlc}" -workers 1 -metadir "$meta" -config PredicateAdmissionAligned.cfg AriadnePredicateAdmission.tla > "$meta/tlc.log" 2>&1 || status=$?
cat "$meta/tlc.log"
printf 'SANY/TLC diagnostic artifacts: %s\n' "$meta"
exit "$status"
