#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/vector-registers-20261013"
 mkdir -p "$out"
 cp "$0" "$out/build-native.sh"
 chown -h jlc:jlc "$out" "$out/build-native.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/vector-registers-20261013/build-native.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-vector-registers-20261013
out=/work/vector-registers-20261013
python3 native/bap-core/build.py --output target/vector-native > "$out/native-build.log" 2>&1
printf '%s\n' 'NATIVE BUILD PASS'
