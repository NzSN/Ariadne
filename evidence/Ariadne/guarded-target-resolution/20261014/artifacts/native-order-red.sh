#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 cp /mnt/d/ariadne-composed-infeasible-test-20261014.ml "$base/work/Repos/Ariadne-composed-20261014/tests/bap/infeasible_loop.ml"
 cp "$0" "$base/work/guarded-target-resolution-20261014/native-order-red.sh"
 chown jlc:jlc "$base/work/Repos/Ariadne-composed-20261014/tests/bap/infeasible_loop.ml" "$base/work/guarded-target-resolution-20261014/native-order-red.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/guarded-target-resolution-20261014/native-order-red.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-composed-20261014
out=/work/guarded-target-resolution-20261014/native-order-red-$(date -u +%Y%m%dT%H%M%S)
mkdir "$out"
sha256sum target/composed-native/capture.ml tests/bap/infeasible_loop.ml > "$out/sources.sha256"
set +e
python3 target/guarded-target-resolution-20261014/run-native-frontier.py --native-dir target/composed-native --test-file tests/bap/infeasible_loop.ml --cases 12 --output target/native-order-red-controls > "$out/test.log" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > "$out/exit-code.txt"
cat "$out/test.log"
printf 'Native order RED artifacts: %s\n' "$out"
