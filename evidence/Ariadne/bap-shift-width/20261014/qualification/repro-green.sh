#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/bap-shift-width-20261014"
 mkdir -p "$out"
 cp /mnt/d/ariadne-shift-width-repro-20261014.rs "$out/repro.rs"
 cp "$0" "$out/repro.sh"
 chown -hR jlc:jlc "$out"
 exec runuser -u jlc -- "$base/run.sh" bash /work/bap-shift-width-20261014/repro.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-bap-shift-count-20261014
python3 - <<'INNER'
from pathlib import Path
import subprocess,os
root=Path.cwd();out=Path('/work/bap-shift-width-20261014');build=root/'target/shift-build/release'
subprocess.run(['rustc','--edition=2024',str(out/'repro.rs'),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'-o',str(out/'repro')],check=True,env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
INNER
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift" BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
set +e
/work/bap-shift-width-20261014/repro > /work/bap-shift-width-20261014/repro-green.log 2>&1
status=$?
cat /work/bap-shift-width-20261014/repro-green.log
exit "$status"
