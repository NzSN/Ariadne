#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/jump-table-check-20261014"
 mkdir -p "$out"
 cp /mnt/d/ariadne-jump-table-check-20261014.rs "$out/check.rs"
 cp "$0" "$out/run.sh"
 chown -R jlc:jlc "$out"
 runuser -u jlc -- "$base/run.sh" bash /work/jump-table-check-20261014/run.sh --inside
 cp "$out/tables.json" /mnt/d/ariadne-jump-table-results-20261014.json
 exit 0
fi
cd /home/nzsn/Repos/Ariadne-request-budget-20261014
out=/work/jump-table-check-20261014
python3 - <<'INNER'
from pathlib import Path
import subprocess,os
root=Path.cwd();out=Path('/work/jump-table-check-20261014');build=root/'target/request-budget-build/release';libs=list((build/'deps').glob('libserde_json-*.rlib'))
subprocess.run(['rustc','--edition=2024',str(out/'check.rs'),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libs[0]),'-o',str(out/'check')],check=True,env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
INNER
"$out/check" /work/frame-paths-dump03958-20261013/original.dmp "$out"
