#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/frame-paths-dump03958-20261013"
 mkdir -p "$out"
 cp /mnt/d/Services/dump-ledger-runtime/data/vault/dump_03958DA4FCA844A786262A1053/original.dmp "$out/original.dmp"
 cp /mnt/d/ariadne-frame-probe-03958-20261013.rs "$out/frame_probe.rs"
 cp "$0" "$out/run.sh"
 chown -h jlc:jlc "$out" "$out/original.dmp" "$out/frame_probe.rs" "$out/run.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/frame-paths-dump03958-20261013/run.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-dump-retry-b5d56b7
out=/work/frame-paths-dump03958-20261013
export ARIADNE_BAP_CORE_DIR="$PWD/target/retry-native"
printf '%s\n' '9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab  /work/frame-paths-dump03958-20261013/original.dmp' | sha256sum --check
printf '%s\n' 'Phase: default frame-to-frame CLI, physical frames 1:0, NP=10'
set +e
/usr/bin/time -v target/retry-build/release/ariadne-minidump "$out/original.dmp" --max-artifact-bytes 2147483648 --decoder-reference target/ariadne-llvm-mc --bap-core-response-timeout-ms 30000 --list-frame-paths 1:0 --path-count-bound 10 --output-dir "$out/cli-default" > "$out/cli-default.log" 2> "$out/cli-default-timing.log"
status=$?
set -e
printf '%s\n' "$status" > "$out/cli-default-exit.txt"
printf '%s\n' 'Phase: compile public API probe with explicit larger recovery bounds'
python3 - <<'COMPILE'
import os,subprocess
from pathlib import Path
root=Path.cwd();build=root/'target/retry-build/release';out=Path('/work/frame-paths-dump03958-20261013')
libs=list((build/'deps').glob('libserde_json-*.rlib'));assert len(libs)==1
subprocess.run(['rustc','--edition=2024',str(out/'frame_probe.rs'),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libs[0]),'-o',str(out/'frame_probe')],check=True,env=dict(os.environ,CARGO_MANIFEST_DIR=str(root)))
COMPILE
printf '%s\n' 'Phase: captured-only frame recovery and bounded path API probe'
set +e
/usr/bin/time -v "$out/frame_probe" "$out/original.dmp" "$out/api-probe" > "$out/api-probe.log" 2> "$out/api-probe-timing.log"
status=$?
set -e
printf '%s\n' "$status" > "$out/api-probe-exit.txt"
printf '%s\n' 'FRAME-PATH ATTEMPTS COMPLETE'
