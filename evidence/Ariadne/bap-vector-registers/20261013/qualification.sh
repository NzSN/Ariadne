#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/vector-registers-20261013"
 repo="$base/work/Repos/Ariadne-vector-registers-20261013"
 cp /mnt/d/ariadne-vector-mutations-20261013.py "$repo/tools/check_bap_vector_mutations.py"
 cp "$0" "$out/qualification.sh"
 chown -h jlc:jlc "$repo/tools/check_bap_vector_mutations.py" "$out/qualification.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/vector-registers-20261013/qualification.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-vector-registers-20261013
out=/work/vector-registers-20261013
export ARIADNE_BAP_CORE_DIR="$PWD/target/vector-native"
export ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc"
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift"
export BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
if [[ -f /home/nzsn/Repos/Ariadne/target/mbt-work/toolchain.json ]]; then
 mkdir -p target/mbt-work
 cp /home/nzsn/Repos/Ariadne/target/mbt-work/toolchain.json target/mbt-work/toolchain.json
fi
set +e
python3 tools/check_bap_core_replay.py --helper-dir target/vector-native --output target/vector-replay-20261013 > "$out/replay.log" 2>&1
replay_status=$?
printf '%s\n' "$replay_status" > "$out/replay-exit.txt"
printf 'REPLAY EXIT %s\n' "$replay_status"
python3 tools/check_bap_vector_mutations.py --output target/vector-mutations-20261013 --seed-build-dir target/vector-build > "$out/vector-mutations.log" 2>&1
mutation_status=$?
printf '%s\n' "$mutation_status" > "$out/mutations-exit.txt"
printf 'VECTOR MUTATIONS EXIT %s\n' "$mutation_status"
tail -12 "$out/vector-mutations.log"
