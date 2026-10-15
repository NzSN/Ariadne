#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
  external=/mnt/d/ariadne-caller-coverage-20261015
  cp /mnt/d/ariadne-caller-legacy-capability-probe-20261015.rs "$external/legacy-capability-probe.rs"
  cp "$0" "$external/legacy-capability-probe.sh"
  chown jlc:jlc "$external/legacy-capability-probe.rs" "$external/legacy-capability-probe.sh"
  exec runuser -u jlc -- bash "$external/run.sh" bash /caller-work/legacy-capability-probe.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-caller-coverage-20261015
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
root=Path.cwd();work=Path('/caller-work')
out=work/'evidence'/('legacy-capability-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir()
source=work/'legacy-capability-probe.rs';runner=work/'legacy-capability-probe.sh'
original=Path('/loop-baseline/repo/target/loop-aware-native')
old=out/'retained-helper';old.mkdir();build=root/'target/caller-build/release'
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(4*1024*1024),b''):h.update(data)
    return h.hexdigest()
manifest_path=work/'source-manifest.json';manifest=json.loads(manifest_path.read_text())
def verify_sources():
    for name,expected in manifest['files'].items():
        if sha(root/name)!=expected:raise RuntimeError('qualified source changed: '+name)
verify_sources()
identities={'ariadne-bap-core':'7f8030820b486dc5a7ec055433d5a7540496c3aaa85fb04c3d91cbdc9e6ec1dd',
            'manifest.json':'204ffe8a8f7585a8f873886b48e64081b6f69a707604e47d758b664c6c872712'}
archived=Path('/loop-baseline/evidence/dump-20261015T051409/native-manifest.json')
assert sha(archived)==identities['manifest.json'],'archived retained manifest changed'
for name,expected in identities.items():
    assert sha(original/name)==expected,'actual retained artifact changed: '+name
    shutil.copyfile(original/name,old/name)
    assert sha(old/name)==expected,'retained copy differs: '+name
(old/'ariadne-bap-core').chmod(0o644)
assert (old/'ariadne-bap-core').stat().st_mode&0o111==0,'retained copy still executable'
assert (build/'libariadne.rlib').is_file(),'qualified release library missing'
libraries=sorted((build/'deps').glob('libserde_json-*.rlib'))
assert libraries,'qualified serde_json library missing'
serde=libraries[0]
command=['rustc','--edition=2024',str(source),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(serde),'-o',str(out/'legacy-capability-probe')]
with (out/'compile.log').open('w') as f:
    subprocess.run(command,check=True,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
with (out/'control.log').open('w') as f:
    subprocess.run(['timeout','60',str(out/'legacy-capability-probe'),str(old),str(out/'result.json')],check=True,stdout=f,stderr=subprocess.STDOUT)
result=json.loads((out/'result.json').read_text())
current_native=root/'target/caller-native/manifest.json'
current_handshake=json.loads(current_native.read_text())['handshake']
for prefix in ['guard_model','guard_engine','composition_model','composition_engine']:
    assert result['current_'+prefix+'_sha256']==current_handshake[prefix+'_sha256'],'linked release proof identity differs: '+prefix
verify_sources()
for name,expected in identities.items():
    assert sha(original/name)==expected and sha(old/name)==expected,'retained artifact changed during control'
shutil.copyfile(source,out/'legacy-capability-probe.rs.txt');shutil.copyfile(runner,out/'legacy-capability-probe.sh')
shutil.copyfile(manifest_path,out/'source-manifest.json');shutil.copyfile(current_native,out/'current-native-manifest.json')
binding={'schema':'ariadne.caller-legacy-capability-source-binding/v1',
    'source_archive_sha256':manifest['archive_sha256'],'source_manifest_sha256':sha(manifest_path),
    'source_files_verified':len(manifest['files']),'sources_unchanged':True,
    'release_library_sha256':sha(build/'libariadne.rlib'),'serde_json_library':serde.name,'serde_json_library_sha256':sha(serde),
    'original_retained_helper_dir':str(original),'original_retained_helper_sha256':identities['ariadne-bap-core'],
    'original_retained_manifest_sha256':identities['manifest.json'],'retained_source_manifest':str(archived),
    'copied_helper_sha256':sha(old/'ariadne-bap-core'),'copied_manifest_sha256':sha(old/'manifest.json'),
    'copied_helper_mode':oct((old/'ariadne-bap-core').stat().st_mode&0o777),'original_unchanged':True,
    'current_native_manifest_sha256':sha(current_native),'driver_sha256':sha(source),
    'driver_binary_sha256':sha(out/'legacy-capability-probe'),'runner_sha256':sha(runner),'compile_command':command,
    'rustc':subprocess.run(['rustc','--version','--verbose'],check=True,text=True,capture_output=True).stdout,
    'scope':'Supplemental new guard2/combined3 capability rejection against the actual loop-generation helper; helper bytes are manifest-bound, copied without execute permission, never launched, and original artifacts unchanged.'}
(out/'source-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
print(json.dumps({'run':str(out),'result':result,'source_binding':binding}),flush=True)
PY
