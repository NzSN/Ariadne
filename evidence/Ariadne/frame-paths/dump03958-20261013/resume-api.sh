#!/bin/bash
set -euo pipefail
cd /home/nzsn/Repos/Ariadne-dump-retry-b5d56b7
out=/work/frame-paths-dump03958-20261013
export ARIADNE_BAP_CORE_DIR="$PWD/target/retry-native"
python3 - <<'COMPILE' > "$out/api-probe-build.log" 2>&1
import os,subprocess
from pathlib import Path
root=Path.cwd();build=root/'target/retry-build/release';out=Path('/work/frame-paths-dump03958-20261013');libs=list((build/'deps').glob('libserde_json-*.rlib'));assert len(libs)==1
subprocess.run(['rustc','--edition=2024',str(out/'frame_probe.rs'),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libs[0]),'-o',str(out/'frame_probe')],check=True,env=dict(os.environ,CARGO_MANIFEST_DIR=str(root)))
COMPILE
printf '%s\n' 'Running captured-only API probe with explicit runtime-table/read/output budgets'
set +e
/usr/bin/time -v "$out/frame_probe" "$out/original.dmp" "$out/api-probe" > "$out/api-probe.log" 2> "$out/api-probe-timing.log"
status=$?
set -e
printf '%s\n' "$status" > "$out/api-probe-exit.txt"
cat "$out/api-probe.log"
tail -10 "$out/api-probe-timing.log"
