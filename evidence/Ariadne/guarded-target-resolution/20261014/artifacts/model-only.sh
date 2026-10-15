#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
  base=/home/jlc/ariadne-p4-20261010
  cp "$0" "$base/work/guarded-target-resolution-20261014/model-only.sh"
  chown jlc:jlc "$base/work/guarded-target-resolution-20261014/model-only.sh"
  exec runuser -u jlc -- "$base/run.sh" bash /work/guarded-target-resolution-20261014/model-only.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-composed-20261014
out=/work/guarded-target-resolution-20261014/model-$(date -u +%Y%m%dT%H%M%S).log
bash Specs/check-guarded-target-resolution.sh > "$out" 2>&1
cat "$out"
