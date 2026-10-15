#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
  external=/mnt/d/ariadne-caller-coverage-20261015
  cp /mnt/d/ariadne-caller-final-dump-admission-20261015.rs "$external/final-dump-admission.rs"
  cp "$0" "$external/final-dump-admission.sh"
  chown jlc:jlc "$external/final-dump-admission.rs" "$external/final-dump-admission.sh"
  exec runuser -u jlc -- bash "$external/run.sh" bash /caller-work/final-dump-admission.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-caller-coverage-20261015
export ARIADNE_BAP_CORE_DIR="$PWD/target/caller-native"
export ARIADNE_LLVM_MC="$PWD/target/caller-llvm/ariadne-llvm-mc"
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift"
export BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
export ARIADNE_TARGET_DIAGNOSTICS=1
export ARIADNE_CALLER_DUMP_ROOT="$PWD"
export ARIADNE_CALLER_DUMP_DRIVER=/caller-work/final-dump-admission.rs
export ARIADNE_CALLER_DUMP_RUN="/caller-work/evidence/final-dump-admission-$(date -u +%Y%m%dT%H%M%S)"
export ARIADNE_CALLER_DUMP_FILE=/work/frame-paths-dump03958-20261013/original.dmp
export ARIADNE_CALLER_DUMP_WITNESS="$PWD/evidence/Ariadne/indirect-target-resolution/dump03958-table-witness-20261014/tables.json"
export ARIADNE_CALLER_DUMP_BASELINE=/caller-work/legacy/guard-v1.json
mkdir "$ARIADNE_CALLER_DUMP_RUN"
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,shutil,subprocess
root=Path(os.environ['ARIADNE_CALLER_DUMP_ROOT'])
out=Path(os.environ['ARIADNE_CALLER_DUMP_RUN'])
driver=Path(os.environ['ARIADNE_CALLER_DUMP_DRIVER'])
build=root/'target/caller-build/release'
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()
manifest_path=Path('/caller-work/source-manifest.json')
manifest=json.loads(manifest_path.read_text())
for name,expected in manifest['files'].items():
    if sha(root/name)!=expected:raise SystemExit('source manifest differs: '+name)
expected=[(Path(os.environ['ARIADNE_CALLER_DUMP_FILE']),'9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab'),
          (Path(os.environ['ARIADNE_CALLER_DUMP_WITNESS']),'1390abca21bb7e2db9cde9a07067f60f5493498a7866fb648dcb103994674baf'),
          (Path(os.environ['ARIADNE_CALLER_DUMP_BASELINE']),'d0294c9b940d8366cb89d78a95d2186c89196dbf1a7955e70189c22afa2abda0'),
          (root/'tests/bap/fixtures/caller-coverage/dump-four-shapes.json','90b440c0059ca65888a5b4b11be69d505763684239118be84fe67e87d99ecb41')]
for path,identity in expected:
    if sha(path)!=identity:raise SystemExit('captured/reference identity differs: '+str(path))
native=root/'target/caller-native'
native_manifest=json.loads((native/'manifest.json').read_text())
if sha(native/'ariadne-bap-core')!=native_manifest['helper_sha256']:
    raise SystemExit('native helper identity differs')
for name,identity in native_manifest['handshake']['source_hashes'].items():
    if sha(root/'native/bap-core'/name)!=identity:raise SystemExit('native source differs: '+name)
loop=hashlib.sha256(('ariadne.loop-target-engine/v1\n'+sha(root/'src/bap/target_resolution.rs')+'\n'+sha(root/'src/bap/target_resolution/loop_closure.rs')+'\n').encode()).hexdigest()
guard_model=sha(root/'Specs/AriadnePredicateAdmission.tla')
guard_engine=hashlib.sha256(('ariadne.guard-checker/v2\n'+sha(root/'src/bap/guard_admission.rs')+'\n'+sha(root/'src/bap/terminal_control.rs')+'\n').encode()).hexdigest()
model=hashlib.sha256(('ariadne.guarded-target-model/v3\n'+sha(root/'Specs/AriadneGuardedTargetResolution.tla')+'\n'+sha(root/'Specs/AriadneLoopTargetClosure.tla')+'\n'+guard_model+'\n').encode()).hexdigest()
checker=hashlib.sha256(('ariadne.guarded-target-checker/v3\n'+sha(root/'src/bap/composition.rs')+'\n'+loop+'\n'+guard_engine+'\n').encode()).hexdigest()
if loop!='afc1b4b991a2bdf402dc8036eb0cfba0d0232505ea5dab31a6e2e2d267a15d95':
    raise SystemExit('qualified loop engine was changed')
for key,value in [('loop_engine_sha256',loop),('guard_model_sha256',guard_model),('guard_engine_sha256',guard_engine),('composition_model_sha256',model),('composition_engine_sha256',checker)]:
    if native_manifest['handshake'][key]!=value:raise SystemExit('native proof identity differs: '+key)
retained=Path('/caller-work/evidence/dump-20261015T073143')
prior_binding=json.loads((retained/'source-binding.json').read_text())
prior_manifest=json.loads((retained/'source-manifest.json').read_text())
prior_result=json.loads((retained/'run-result.json').read_text())
prior_native=json.loads((retained/'native-manifest.json').read_text())
if sha(retained/'source-manifest.json')!=prior_binding['source_manifest_sha256'] or sha(retained/'native-manifest.json')!=prior_binding['native_manifest_sha256']:
    raise SystemExit('retained source/helper manifests differ from prior binding')
if not prior_result['sources_unchanged'] or prior_result['probe_exit_code']!=0:
    raise SystemExit('retained bounded full run did not finish without source drift')
for name,identity in manifest['files'].items():
    if name.startswith('src/') and prior_manifest['files'].get(name)!=identity:
        raise SystemExit('current Rust source differs from retained bounded full run: '+name)
for name,identity in native_manifest['handshake']['source_hashes'].items():
    if name!='legacy_guard.ml' and prior_native['handshake']['source_hashes'].get(name)!=identity:
        raise SystemExit('current native rules differ from retained bounded full run: '+name)
for key in ['guard_model_sha256','guard_engine_sha256','composition_model_sha256','composition_engine_sha256','loop_model_sha256','loop_engine_sha256']:
    if native_manifest['handshake'][key]!=prior_native['handshake'][key]:
        raise SystemExit('current modeled proof identity differs from retained bounded full run: '+key)
retained_artifacts={}
for index in [1,0]:
    frame=retained/('frame-'+str(index))
    identities=[json.loads(line)for line in (frame/'artifact-identities.ndjson').read_text().splitlines()]
    for original in ['prepared-full.json','guard-report.json','target-report.json','composition-report.json','outcome.json']:
        rows=[row for row in identities if row['original']==original]
        if len(rows)!=1:raise SystemExit('retained artifact identity absent or duplicated: '+original)
        row=rows[0];path=frame/row['stored']
        if path.suffix=='.gz':
            import gzip
            data=gzip.decompress(path.read_bytes())
        else:data=path.read_bytes()
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise SystemExit('retained artifact bytes differ: '+str(path))
        retained_artifacts[str(path.relative_to(retained))]={'stored_sha256':sha(path),'original_sha256':row['sha256'],'original_bytes':row['bytes']}
libraries=sorted((build/'deps').glob('libserde_json-*.rlib'))
if not libraries or not (build/'libariadne.rlib').exists():raise SystemExit('qualified release library missing')
command=['rustc','--edition=2024',str(driver),'-O','-L','dependency='+str(build/'deps'),
         '--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libraries[0]),
         '-o','/caller-work/final-dump-admission']
with (out/'compile.log').open('w') as log:
    subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,
                   env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
shutil.copyfile(manifest_path,out/'source-manifest.json')
shutil.copyfile(native/'manifest.json',out/'native-manifest.json')
shutil.copyfile(driver,out/'final-dump-admission.rs.txt')
shutil.copyfile(Path('/caller-work/final-dump-admission.sh'),out/'final-dump-admission.sh')
binding={'schema':'ariadne.caller-final-helper-dump-source-binding/v1',
         'dump_url':'https://192.168.150.219:4080/dumps/dump_03958DA4FCA844A786262A1053',
         'dump_sha256':expected[0][1],'frozen_table_witness_sha256':expected[1][1],
         'historical_guard_sha256':expected[2][1],'caller_expectation_sha256':expected[3][1],
         'source_manifest_sha256':sha(manifest_path),'source_files_verified':len(manifest['files']),
         'source_archive_sha256':manifest['archive_sha256'],'source_manifest_artifact':'source-manifest.json',
         'native_manifest_sha256':sha(native/'manifest.json'),'native_manifest_artifact':'native-manifest.json',
         'native_helper_sha256':native_manifest['helper_sha256'],
         'loop_engine_sha256':loop,'guard_model_sha256':guard_model,'guard_engine_sha256':guard_engine,
         'composition_model_sha256':model,'composition_engine_sha256':checker,
         'loop_model_sha256':sha(root/'Specs/AriadneLoopTargetClosure.tla'),
         'driver_sha256':sha(driver),'driver_binary_sha256':sha(Path('/caller-work/final-dump-admission')),
         'runner_sha256':sha(Path('/caller-work/final-dump-admission.sh')),
         'release_library_sha256':sha(build/'libariadne.rlib'),
         'serde_json_library':libraries[0].name,'serde_json_library_sha256':sha(libraries[0]),
         'tool_hashes':{name:sha(path) for name,path in [('ariadne-bap-lift',root/'target/ariadne-bap-lift'),('ariadne-llvm-mc',root/'target/caller-llvm/ariadne-llvm-mc')]},
         'rustc':subprocess.run(['rustc','--version','--verbose'],check=True,text=True,capture_output=True).stdout,
         'compile_command':command,'retained_current_run':str(retained),
         'retained_current_source_binding_sha256':sha(retained/'source-binding.json'),
         'retained_current_source_manifest_sha256':sha(retained/'source-manifest.json'),
         'retained_current_native_manifest_sha256':sha(retained/'native-manifest.json'),
         'retained_current_artifacts':retained_artifacts,
         'retained_library_sha256':prior_binding['release_library_sha256'],
         'current_library_identical_to_retained':sha(build/'libariadne.rlib')==prior_binding['release_library_sha256'],
         'current_rust_sources_unchanged_from_retained':True,'only_native_checker_change_allowed':'legacy_guard.ml',
         'diagnostic_completion_limits':{'caller_rust':'stop after structural recovery, at PhaseDataflow','caller_native':'initialize only, completion not attempted','callee_rust_actions':1000000,'callee_rust_deadline_seconds':600,'callee_native_actions':1000000,'native_response_timeout_seconds':600,'process_timeout_seconds':2400},
         'claim_boundary':'Fresh final-helper caller admission and structural recovery only; no fresh caller full-state parity. Full callee comparison. Exact request/proofs compared with source-bound073143 bounded full run; original production budgets/roots/premises remain unchanged.'}
(out/'source-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
print(json.dumps({'run':str(out),'source_files_verified':len(manifest['files']),
                  'driver_sha256':binding['driver_sha256'],'native_helper_sha256':binding['native_helper_sha256']}),flush=True)
PY
set +e
/usr/bin/time -v timeout 2400 /caller-work/final-dump-admission "$ARIADNE_CALLER_DUMP_FILE" \
  "$ARIADNE_CALLER_DUMP_RUN" "$ARIADNE_CALLER_DUMP_WITNESS" "$ARIADNE_CALLER_DUMP_BASELINE" paths \
  > "$ARIADNE_CALLER_DUMP_RUN/probe.log" 2> "$ARIADNE_CALLER_DUMP_RUN/timing.log"
probe_exit=$?
set -e
export ARIADNE_CALLER_DUMP_EXIT="$probe_exit"
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os
root=Path(os.environ['ARIADNE_CALLER_DUMP_ROOT']);out=Path(os.environ['ARIADNE_CALLER_DUMP_RUN'])
manifest=json.loads((out/'source-manifest.json').read_text())
changed=[name for name,expected in manifest['files'].items()
         if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected]
result={'probe_exit_code':int(os.environ['ARIADNE_CALLER_DUMP_EXIT']),
        'source_files_verified':len(manifest['files']),'sources_unchanged':not changed,'changed_sources':changed}
(out/'run-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if changed:raise SystemExit('source drift during original dump retry')
PY
cat "$ARIADNE_CALLER_DUMP_RUN/probe.log"
exit "$probe_exit"
