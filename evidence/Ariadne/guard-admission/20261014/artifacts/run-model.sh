#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/guard-admission-20261014"
 cp "$0" "$out/run-model.sh"
 chown -h jlc:jlc "$out/run-model.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/guard-admission-20261014/run-model.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-guard-admission-20261014
set +e
bash Specs/check-predicate-admission.sh > /work/guard-admission-20261014/model.log 2>&1
status=$?
printf '%s\n' "$status" > /work/guard-admission-20261014/model-exit.txt
tail -n 25 /work/guard-admission-20261014/model.log
exit "$status"
