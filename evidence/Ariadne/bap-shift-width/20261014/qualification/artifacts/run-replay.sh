#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/bap-shift-width-20261014"
 cp "$0" "$out/run-replay.sh";chown jlc:jlc "$out/run-replay.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/bap-shift-width-20261014/run-replay.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-bap-shift-count-20261014
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_BUILD_JOBS=2
mkdir -p target/mbt-work
ln -sfn /home/nzsn/Repos/Ariadne/target/mbt-work/toolchain.json target/mbt-work/toolchain.json
python3 tools/check_bap_core_replay.py --helper-dir target/shift-native --output /work/bap-shift-width-20261014/replay > /work/bap-shift-width-20261014/replay.log 2>&1
cat /work/bap-shift-width-20261014/replay.log
