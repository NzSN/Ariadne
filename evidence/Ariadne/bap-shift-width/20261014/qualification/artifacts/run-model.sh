#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/bap-shift-width-20261014"
 cp "$0" "$out/run-model.sh";chown jlc:jlc "$out/run-model.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/bap-shift-width-20261014/run-model.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-bap-shift-count-20261014
bash Specs/check-predicate-admission.sh > /work/bap-shift-width-20261014/model.log 2>&1
 tail -n 10 /work/bap-shift-width-20261014/model.log
