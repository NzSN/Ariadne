#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/guard-admission-20261014"
 cp "$0" "$out/initial-build.sh"
 chown -h jlc:jlc "$out/initial-build.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/guard-admission-20261014/initial-build.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-guard-admission-20261014
out=/work/guard-admission-20261014
export CARGO_TARGET_DIR="$PWD/target/guard-build"
export CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0
export ARIADNE_BAP_CORE_DIR="$PWD/target/guard-native"
set +e
cargo test --offline --locked --lib guard_admission > "$out/initial-rust.log" 2>&1
rust_status=$?
printf '%s\n' "$rust_status" > "$out/initial-rust-exit.txt"
printf 'INITIAL RUST EXIT %s\n' "$rust_status"
tail -n 35 "$out/initial-rust.log"
python3 native/bap-core/build.py --output target/guard-native > "$out/initial-native.log" 2>&1
native_status=$?
printf '%s\n' "$native_status" > "$out/initial-native-exit.txt"
printf 'INITIAL NATIVE EXIT %s\n' "$native_status"
tail -n 20 "$out/initial-native.log"
