#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
  external=/mnt/d/ariadne-loop-aware-20261015
  staged=/mnt/d/ariadne-loop-aware-legacy-capability-old
  mkdir -p "$external/legacy-capability-helper"
  cp /mnt/d/ariadne-loop-aware-legacy-capability-probe-20261015.rs "$external/legacy-capability-probe.rs"
  cp "$0" "$external/legacy-capability-probe.sh"
  cp "$staged/ariadne-bap-core" "$staged/manifest.json" "$external/legacy-capability-helper/"
  chmod 0644 "$external/legacy-capability-helper/ariadne-bap-core"
  chown -R jlc:jlc "$external/legacy-capability-helper" "$external/legacy-capability-probe.rs" "$external/legacy-capability-probe.sh"
  exec runuser -u jlc -- bash "$external/run.sh" bash /loop-work/legacy-capability-probe.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-loop-aware-20261015
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
root=Path.cwd();work=Path('/loop-work')
out=work/'evidence'/('legacy-capability-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir()
source=work/'legacy-capability-probe.rs';runner=work/'legacy-capability-probe.sh'
old=work/'legacy-capability-helper';build=root/'target/loop-aware-build/release'
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(4*1024*1024),b''):h.update(data)
    return h.hexdigest()
manifest_path=work/'source-manifest.json';manifest=json.loads(manifest_path.read_text())
assert manifest['archive_sha256']=='5cd406c5181d131679a60af15f53edcabecfe056144e40b5785bc37ce1d010ee'
assert sha(manifest_path)=='7e16611a5fb938916209c34f2c8d73e58b267e50f64e0ebb84ce5735a8287e90'
def verify_sources():
    for name,expected in manifest['files'].items():
        if sha(root/name)!=expected:raise RuntimeError('qualified source changed: '+name)
verify_sources()
assert sha(build/'libariadne.rlib')=='9351a0e9e3d56a33088e8f50334eb0a711e3316f1983cd111e3b41a3fd8937a3'
assert sha(old/'ariadne-bap-core')=='cc9ff8718659af45e3d86ba0949915615f8bdb64822638597522af63dba0c0f8'
assert sha(old/'manifest.json')=='70d7a8ee8a6c3d30b214349208524676b1038dd9544c5f225def51a2b68c2798'
serde=build/'deps/libserde_json-540ae372bafb180c.rlib'
assert sha(serde)=='536308274fbc56cf511a66b3c030d86566328a86d725c8c14210a09966fb4bb4'
command=['rustc','--edition=2024',str(source),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(serde),'-o',str(out/'legacy-capability-probe')]
with (out/'compile.log').open('w') as f:
    subprocess.run(command,check=True,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
with (out/'control.log').open('w') as f:
    subprocess.run([str(out/'legacy-capability-probe'),str(old),str(out/'result.json')],check=True,stdout=f,stderr=subprocess.STDOUT)
verify_sources()
shutil.copyfile(source,out/'legacy-capability-probe.rs.txt');shutil.copyfile(runner,out/'legacy-capability-probe.sh')
shutil.copyfile(manifest_path,out/'source-manifest.json');shutil.copyfile(old/'manifest.json',out/'retained-native-manifest.json')
binding={'schema':'ariadne.legacy-combined-capability-source-binding/v1','source_archive_sha256':manifest['archive_sha256'],'source_manifest_sha256':sha(manifest_path),'source_files_verified':len(manifest['files']),'sources_unchanged':True,'release_library_sha256':sha(build/'libariadne.rlib'),'serde_json_library_sha256':sha(serde),'retained_helper_sha256':sha(old/'ariadne-bap-core'),'retained_manifest_sha256':sha(old/'manifest.json'),'driver_sha256':sha(source),'driver_binary_sha256':sha(out/'legacy-capability-probe'),'runner_sha256':sha(runner),'compile_command':command,'rustc':subprocess.run(['rustc','--version','--verbose'],check=True,text=True,capture_output=True).stdout,'scope':'Supplemental old-helper capability rejection; qualified production source/library bytes unchanged; old helper is not launched.'}
(out/'source-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
print(json.dumps({'run':str(out),'result':json.loads((out/'result.json').read_text()),'source_binding':binding}),flush=True)
PY
