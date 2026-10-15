#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 cp /mnt/d/ariadne-composed-target-regression-20261014.rs "$base/work/Repos/Ariadne-composed-20261014/tests/bap/target_resolution_unit.rs"
 cp "$0" "$base/work/guarded-target-resolution-20261014/red-only.sh"
 chown jlc:jlc "$base/work/Repos/Ariadne-composed-20261014/tests/bap/target_resolution_unit.rs" "$base/work/guarded-target-resolution-20261014/red-only.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/guarded-target-resolution-20261014/red-only.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-composed-20261014
export CARGO_TARGET_DIR="$PWD/target/composed-build" CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_BUILD_JOBS=4
out=/work/guarded-target-resolution-20261014/conditional-write-red-$(date -u +%Y%m%dT%H%M%S)
mkdir "$out"
sha256sum src/bap/target_resolution.rs tests/bap/target_resolution_unit.rs > "$out/sources.sha256"
set +e
cargo test --offline --locked --lib conditional_write_predicate_is_not_rewritten_twice > "$out/test.log" 2>&1
rc=$?
set -e
printf '%s\n' "$rc" > "$out/exit-code.txt"
cat "$out/test.log"
printf 'RED control artifacts: %s\n' "$out"
