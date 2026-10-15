#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/guard-budget-config-20261014"
 cp /mnt/d/ariadne-guard-budget-prepare-probe-20261014.rs "$out/prepare-probe.rs"
 cp "$0" "$out/run-probe.sh"
 chown jlc:jlc "$out/prepare-probe.rs" "$out/run-probe.sh"
 exec runuser -u jlc -- "$base/run.sh" bash /work/guard-budget-config-20261014/run-probe.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-guard-budget-20261014
export ARIADNE_BAP_CORE_DIR="$PWD/target/guard-budget-native" ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc"
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift" BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
out=/work/guard-budget-config-20261014
dump=/work/frame-paths-dump03958-20261013/original.dmp
printf '%s\n' "9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab  $dump" | sha256sum --check
python3 - <<'INNER'
from pathlib import Path
import subprocess,os
root=Path.cwd();out=Path('/work/guard-budget-config-20261014');build=root/'target/guard-budget-build/release';libs=list((build/'deps').glob('libserde_json-*.rlib'))
subprocess.run(['rustc','--edition=2024',str(out/'prepare-probe.rs'),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libs[0]),'-o',str(out/'prepare-probe')],check=True,env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
INNER
for mode in original-discovery expanded; do
 /usr/bin/time -v timeout 180 "$out/prepare-probe" "$dump" "$out/probe-$mode" "$mode" > "$out/probe-$mode.log" 2> "$out/probe-$mode-timing.log"
 cat "$out/probe-$mode.log"
done
