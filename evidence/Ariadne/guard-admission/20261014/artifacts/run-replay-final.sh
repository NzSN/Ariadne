#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/guard-admission-20261014"
 cp "$0" "$out/run-replay-final.sh"
 chown jlc:jlc "$out/run-replay-final.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/guard-admission-20261014/run-replay-final.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-guard-admission-20261014
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_BUILD_JOBS=2
python3 tools/check_bap_core_replay.py --helper-dir target/guard-native --output /work/guard-admission-20261014/replay-final > /work/guard-admission-20261014/replay-final.log 2>&1
cat /work/guard-admission-20261014/replay-final.log
