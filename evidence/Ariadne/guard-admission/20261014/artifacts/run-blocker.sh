#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/guard-admission-20261014"
 cp "$0" "$out/run-blocker.sh"
 cp /mnt/d/ariadne-guard-blocker-probe-20261014.rs "$out/blocker_probe.rs"
 chown jlc:jlc "$out/run-blocker.sh" "$out/blocker_probe.rs"
 exec runuser -u jlc -- "$base/run.sh" bash /work/guard-admission-20261014/run-blocker.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-guard-admission-20261014
export CARGO_INCREMENTAL=0
export CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_BUILD_JOBS=2
export CARGO_TARGET_DIR="$PWD/target/guard-build"
export ARIADNE_BAP_CORE_DIR="$PWD/target/guard-native" ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc"
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift" BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
out=/work/guard-admission-20261014
dump=/work/frame-paths-dump03958-20261013/original.dmp
printf '%s\n' "9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab  $dump" | sha256sum --check
python3 - <<'INNER'
from pathlib import Path
import subprocess,os
root=Path.cwd();out=Path('/work/guard-admission-20261014');build=root/'target/guard-build/release'
libs=list((build/'deps').glob('libserde_json-*.rlib'))
subprocess.run(['rustc','--edition=2024',str(out/'blocker_probe.rs'),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libs[0]),'-o',str(out/'blocker_probe')],check=True,env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
INNER
timeout 300 "$out/blocker_probe" "$dump" "$out/next-blocker.json" > "$out/next-blocker.log" 2>&1
cat "$out/next-blocker.log"
