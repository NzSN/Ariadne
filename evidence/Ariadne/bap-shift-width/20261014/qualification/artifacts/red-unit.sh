#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/bap-shift-width-20261014"
 cp "$0" "$out/red-unit.sh"
 chown jlc:jlc "$out/red-unit.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/bap-shift-width-20261014/red-unit.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-bap-shift-count-20261014
export CARGO_TARGET_DIR="$PWD/target/shift-build" CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_BUILD_JOBS=4
set +e
cargo test --offline --locked --lib bap::shift_projection_tests -- --nocapture > /work/bap-shift-width-20261014/red-unit.log 2>&1
status=$?
cat /work/bap-shift-width-20261014/red-unit.log
exit "$status"
