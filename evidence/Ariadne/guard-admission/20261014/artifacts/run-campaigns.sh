#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/guard-admission-20261014"
 cp "$0" "$out/run-campaigns.sh"
 chown jlc:jlc "$out/run-campaigns.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/guard-admission-20261014/run-campaigns.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-guard-admission-20261014
export CARGO_INCREMENTAL=0
export CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0
export CARGO_TARGET_DIR="$PWD/target/guard-build" CARGO_BUILD_JOBS=2
export ARIADNE_BAP_CORE_DIR="$PWD/target/guard-native"
export ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc" ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift"
export BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
out=/work/guard-admission-20261014
mkdir -p target/mbt-work
ln -sfn /home/nzsn/Repos/Ariadne/target/mbt-work/toolchain.json target/mbt-work/toolchain.json
printf 'Starting focused guard mutations\n'
python3 tools/check_guard_admission_mutations.py --output target/guard-mutations-20261014 --seed-build-dir target/guard-build --build-jobs 2 > "$out/guard-mutations.log" 2>&1
cat "$out/guard-mutations.log"
python3 tools/check_bap_core_replay.py --helper-dir target/guard-native --output "$out/replay" > "$out/replay.log" 2>&1
cat "$out/replay.log"
