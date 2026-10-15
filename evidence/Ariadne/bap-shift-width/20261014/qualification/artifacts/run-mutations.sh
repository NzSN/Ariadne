#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 repo="$base/work/Repos/Ariadne-bap-shift-count-20261014"
 out="$base/work/bap-shift-width-20261014"
 cp /mnt/d/ariadne-shift-mutations-20261014.py "$repo/tools/check_bap_shift_mutations.py"
 cp "$0" "$out/run-mutations.sh"
 chown jlc:jlc "$repo/tools/check_bap_shift_mutations.py" "$out/run-mutations.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/bap-shift-width-20261014/run-mutations.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-bap-shift-count-20261014
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0
out=/work/bap-shift-width-20261014
python3 tools/check_bap_shift_mutations.py --output target/shift-mutations-v2-20261014 --seed-build-dir target/shift-build --native --helper target/ariadne-bap-lift --decoder target/ariadne-llvm-mc --runtime-root tmp/bap-setup/stable --build-jobs 2 > "$out/mutations-v2.log" 2>&1
cat "$out/mutations-v2.log"
