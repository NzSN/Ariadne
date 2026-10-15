#!/bin/bash
set -euo pipefail
external=/mnt/d/ariadne-caller-coverage-20261015
if [[ ${1:-} != --inside ]]; then
 cp /mnt/d/ariadne-case4-probe-20261015.rs "$external/case4-probe.rs"
 cp "$0" "$external/case4-run.sh"
 chown jlc:jlc "$external/case4-probe.rs" "$external/case4-run.sh"
 exec runuser -u jlc -- bash "$external/run.sh" bash /caller-work/case4-run.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-caller-coverage-20261015
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift"
export BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
export ARIADNE_LLVM_MC="$PWD/target/caller-llvm/ariadne-llvm-mc"
python3 - <<'PY'
from pathlib import Path
import hashlib,json,subprocess,os,time
root=Path.cwd();out=Path('/caller-work/evidence')/('case4-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir();print('Case4 evidence:',out,flush=True)
m=json.loads(Path('/caller-work/source-manifest.json').read_text())
for n,h in m['files'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h,n
(out/'source-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
build=root/'target/caller-build/release';serde=sorted((build/'deps').glob('libserde_json-*.rlib'))[0]
cmd=['rustc','--edition=2024','/caller-work/case4-probe.rs','-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(serde),'-o','/caller-work/case4-probe']
with(out/'compile.log').open('w')as f:p=subprocess.run(cmd,env={**os.environ,'CARGO_MANIFEST_DIR':str(root)},stdout=f,stderr=subprocess.STDOUT)
if p.returncode:print((out/'compile.log').read_text());raise SystemExit(p.returncode)
command=['timeout','240','/caller-work/case4-probe','/work/frame-paths-dump03958-20261013/original.dmp',str(out),'--assert-complete']
with(out/'probe.log').open('w')as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
changed=[n for n,h in m['files'].items()if hashlib.sha256((root/n).read_bytes()).hexdigest()!=h]
result={'exit_code':r.returncode,'sources_unchanged':not changed,'changed':changed,'compile_command':cmd,'probe_command':command,'driver_sha256':hashlib.sha256(Path('/caller-work/case4-probe.rs').read_bytes()).hexdigest(),'release_library_sha256':hashlib.sha256((build/'libariadne.rlib').read_bytes()).hexdigest()}
(out/'run-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);print((out/'probe.log').read_text()[-7000:])
raise SystemExit(r.returncode)
PY
