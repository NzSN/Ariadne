#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
  external=/mnt/d/ariadne-loop-aware-20261015
  cp /mnt/d/ariadne-loop-aware-dump-probe-20261015.rs "$external/dump-probe.rs"
  cp "$0" "$external/run-dump-probe.sh"
  chown jlc:jlc "$external/dump-probe.rs" "$external/run-dump-probe.sh"
  exec runuser -u jlc -- bash "$external/run.sh" bash /loop-work/run-dump-probe.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-loop-aware-20261015
export ARIADNE_BAP_CORE_DIR="$PWD/target/loop-aware-native"
export ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc"
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift"
export BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
export ARIADNE_TARGET_DIAGNOSTICS=1
export ARIADNE_LOOP_DUMP_ROOT="$PWD"
export ARIADNE_LOOP_DUMP_DRIVER=/loop-work/dump-probe.rs
export ARIADNE_LOOP_DUMP_RUN="/loop-work/evidence/dump-$(date -u +%Y%m%dT%H%M%S)"
export ARIADNE_LOOP_DUMP_FILE=/work/frame-paths-dump03958-20261013/original.dmp
export ARIADNE_LOOP_DUMP_WITNESS="$PWD/evidence/Ariadne/indirect-target-resolution/dump03958-table-witness-20261014/tables.json"
export ARIADNE_LOOP_DUMP_BASELINE=/work/native-request-budget-20261014/probe-expanded/guard-report.json
mkdir "$ARIADNE_LOOP_DUMP_RUN"
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,shutil,subprocess
root=Path(os.environ['ARIADNE_LOOP_DUMP_ROOT'])
out=Path(os.environ['ARIADNE_LOOP_DUMP_RUN'])
driver=Path(os.environ['ARIADNE_LOOP_DUMP_DRIVER'])
build=root/'target/loop-aware-build/release'
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()
manifest_path=Path('/loop-work/source-manifest.json')
manifest=json.loads(manifest_path.read_text())
for name,expected in manifest['files'].items():
    if sha(root/name)!=expected:raise SystemExit('source manifest differs: '+name)
expected=[(Path(os.environ['ARIADNE_LOOP_DUMP_FILE']),'9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab'),
          (Path(os.environ['ARIADNE_LOOP_DUMP_WITNESS']),'1390abca21bb7e2db9cde9a07067f60f5493498a7866fb648dcb103994674baf'),
          (Path(os.environ['ARIADNE_LOOP_DUMP_BASELINE']),'d0294c9b940d8366cb89d78a95d2186c89196dbf1a7955e70189c22afa2abda0')]
for path,identity in expected:
    if sha(path)!=identity:raise SystemExit('captured/reference identity differs: '+str(path))
native=root/'target/loop-aware-native'
native_manifest=json.loads((native/'manifest.json').read_text())
if sha(native/'ariadne-bap-core')!=native_manifest['helper_sha256']:
    raise SystemExit('native helper identity differs')
for name,identity in native_manifest['handshake']['source_hashes'].items():
    if sha(root/'native/bap-core'/name)!=identity:raise SystemExit('native source differs: '+name)
loop=hashlib.sha256(('ariadne.loop-target-engine/v1\n'+sha(root/'src/bap/target_resolution.rs')+'\n'+sha(root/'src/bap/target_resolution/loop_closure.rs')+'\n').encode()).hexdigest()
model=hashlib.sha256(('ariadne.guarded-target-model/v2\n'+sha(root/'Specs/AriadneGuardedTargetResolution.tla')+'\n'+sha(root/'Specs/AriadneLoopTargetClosure.tla')+'\n').encode()).hexdigest()
checker=hashlib.sha256(('ariadne.guarded-target-checker/v2\n'+sha(root/'src/bap/composition.rs')+'\n'+loop+'\n').encode()).hexdigest()
for key,value in [('loop_engine_sha256',loop),('composition_model_sha256',model),('composition_engine_sha256',checker)]:
    if native_manifest['handshake'][key]!=value:raise SystemExit('native proof identity differs: '+key)
libraries=sorted((build/'deps').glob('libserde_json-*.rlib'))
if not libraries or not (build/'libariadne.rlib').exists():raise SystemExit('qualified release library missing')
command=['rustc','--edition=2024',str(driver),'-O','-L','dependency='+str(build/'deps'),
         '--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libraries[0]),
         '-o','/loop-work/dump-probe']
with (out/'compile.log').open('w') as log:
    subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,
                   env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
shutil.copyfile(manifest_path,out/'source-manifest.json')
shutil.copyfile(native/'manifest.json',out/'native-manifest.json')
shutil.copyfile(driver,out/'dump-probe.rs.txt')
shutil.copyfile(Path('/loop-work/run-dump-probe.sh'),out/'run-dump-probe.sh')
binding={'schema':'ariadne.loop-aware-dump-source-binding/v1',
         'dump_url':'https://192.168.150.219:4080/dumps/dump_03958DA4FCA844A786262A1053',
         'dump_sha256':expected[0][1],'frozen_table_witness_sha256':expected[1][1],
         'historical_guard_sha256':expected[2][1],
         'source_manifest_sha256':sha(manifest_path),'source_files_verified':len(manifest['files']),
         'source_archive_sha256':manifest['archive_sha256'],'source_manifest_artifact':'source-manifest.json',
         'native_manifest_sha256':sha(native/'manifest.json'),'native_manifest_artifact':'native-manifest.json',
         'native_helper_sha256':native_manifest['helper_sha256'],
         'loop_engine_sha256':loop,'composition_model_sha256':model,'composition_engine_sha256':checker,
         'loop_model_sha256':sha(root/'Specs/AriadneLoopTargetClosure.tla'),
         'driver_sha256':sha(driver),'driver_binary_sha256':sha(Path('/loop-work/dump-probe')),
         'runner_sha256':sha(Path('/loop-work/run-dump-probe.sh')),
         'release_library_sha256':sha(build/'libariadne.rlib'),
         'serde_json_library':libraries[0].name,'serde_json_library_sha256':sha(libraries[0]),
         'tool_hashes':{name:sha(root/'target'/name) for name in ['ariadne-bap-lift','ariadne-llvm-mc']},
         'rustc':subprocess.run(['rustc','--version','--verbose'],check=True,text=True,capture_output=True).stdout,
         'compile_command':command,'claim_boundary':'Fresh original-dump scoped retry; downstream partial/unavailable outcomes remain explicit.'}
(out/'source-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
print(json.dumps({'run':str(out),'source_files_verified':len(manifest['files']),
                  'driver_sha256':binding['driver_sha256'],'native_helper_sha256':binding['native_helper_sha256']}),flush=True)
PY
set +e
/usr/bin/time -v timeout 900 /loop-work/dump-probe "$ARIADNE_LOOP_DUMP_FILE" \
  "$ARIADNE_LOOP_DUMP_RUN" "$ARIADNE_LOOP_DUMP_WITNESS" "$ARIADNE_LOOP_DUMP_BASELINE" paths \
  > "$ARIADNE_LOOP_DUMP_RUN/probe.log" 2> "$ARIADNE_LOOP_DUMP_RUN/timing.log"
probe_exit=$?
set -e
export ARIADNE_LOOP_DUMP_EXIT="$probe_exit"
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os
root=Path(os.environ['ARIADNE_LOOP_DUMP_ROOT']);out=Path(os.environ['ARIADNE_LOOP_DUMP_RUN'])
manifest=json.loads((out/'source-manifest.json').read_text())
changed=[name for name,expected in manifest['files'].items()
         if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected]
result={'probe_exit_code':int(os.environ['ARIADNE_LOOP_DUMP_EXIT']),
        'source_files_verified':len(manifest['files']),'sources_unchanged':not changed,'changed_sources':changed}
(out/'run-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if changed:raise SystemExit('source drift during original dump retry')
PY
cat "$ARIADNE_LOOP_DUMP_RUN/probe.log"
exit "$probe_exit"
