#!/bin/bash
set -euo pipefail
cd /home/nzsn/Repos/Ariadne-dump-retry-b5d56b7
out=/work/frame-paths-dump03958-20261013
python3 - <<'BUILD'
from pathlib import Path
import os,subprocess
root=Path.cwd();b=root/'target/retry-build/release';o=Path('/work/frame-paths-dump03958-20261013');j=list((b/'deps').glob('libserde_json-*.rlib'))[0]
subprocess.run(['rustc','--edition=2024',str(o/'blocker_probe.rs'),'-O','-L','dependency='+str(b/'deps'),'--extern','ariadne='+str(b/'libariadne.rlib'),'-o',str(o/'blocker_probe')],check=True,env=dict(os.environ,CARGO_MANIFEST_DIR=str(root)))
BUILD
"$out/blocker_probe" "$out/original.dmp" "$out/blocker-instruction.json"
python3 - <<'SHOW'
import json
from pathlib import Path
r=json.loads(Path('/work/frame-paths-dump03958-20261013/blocker-instruction.json').read_text());print(json.dumps(r['preparation'],indent=2));print(r['analysis']['obligations'])
SHOW
