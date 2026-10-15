#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
  external=/mnt/d/ariadne-caller-coverage-20261015
  for name in extract.py barrier-probe-current.rs run-feedback-current.sh; do
    cp "/mnt/d/ariadne-caller-barriers-20261015-$name" "$external/caller-barriers-$name"
    chown jlc:jlc "$external/caller-barriers-$name"
  done
  exec runuser -u jlc -- bash "$external/run.sh" bash /caller-work/caller-barriers-run-feedback-current.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-caller-coverage-20261015
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift"
export BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
export ARIADNE_LLVM_MC="$PWD/target/caller-llvm/ariadne-llvm-mc"
export ARIADNE_CALLER_FEEDBACK_RUN="/caller-work/evidence/caller-barriers-$(date -u +%Y%m%dT%H%M%S)"
mkdir "$ARIADNE_CALLER_FEEDBACK_RUN"
python3 /caller-work/caller-barriers-extract.py --run /loop-baseline/evidence/dump-20261015T051409 --output "$ARIADNE_CALLER_FEEDBACK_RUN/extracted" \
  > "$ARIADNE_CALLER_FEEDBACK_RUN/extraction.log" 2>&1
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os,subprocess
root=Path.cwd();out=Path(os.environ['ARIADNE_CALLER_FEEDBACK_RUN'])
build=root/'target/caller-build/release'
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()
manifest_path=Path('/caller-work/source-manifest.json');manifest=json.loads(manifest_path.read_text())
for name,identity in manifest['files'].items():
    if sha(root/name)!=identity:raise SystemExit('source manifest differs: '+name)
libraries=sorted((build/'deps').glob('libserde_json-*.rlib'))
if not libraries:raise SystemExit('qualified serde_json release dependency absent')
driver=Path('/caller-work/caller-barriers-barrier-probe-current.rs')
command=['rustc','--edition=2024',str(driver),'-O','-L','dependency='+str(build/'deps'),
         '--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libraries[0]),
         '-o','/caller-work/caller-barriers-probe']
with (out/'compile.log').open('w') as log:
    subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,
                   env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
record={'schema':'ariadne.caller-barrier-feedback-source-binding/v1',
        'source_manifest_sha256':sha(manifest_path),'source_files_verified':len(manifest['files']),
        'source_archive_sha256':manifest['archive_sha256'],'release_library_sha256':sha(build/'libariadne.rlib'),
        'driver_sha256':sha(driver),'driver_binary_sha256':sha(Path('/caller-work/caller-barriers-probe')),
        'tool_hashes':{name:sha(root/'target'/name) for name in ['ariadne-bap-lift','caller-llvm/ariadne-llvm-mc']},
        'fixture_sha256':sha(out/'extracted/four-shapes.json'),'compile_command':command,
        'scope':'Post-correction four-shape feedback; not whole-caller closure or alignment proof.'}
(out/'source-binding.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'run':str(out),'source_files_verified':len(manifest['files'])}),flush=True)
PY
set +e
/usr/bin/time -v timeout 180 /caller-work/caller-barriers-probe \
  /work/frame-paths-dump03958-20261013/original.dmp \
  "$ARIADNE_CALLER_FEEDBACK_RUN/extracted/four-shapes.json" "$ARIADNE_CALLER_FEEDBACK_RUN" --assert-closed \
  > "$ARIADNE_CALLER_FEEDBACK_RUN/probe.log" 2> "$ARIADNE_CALLER_FEEDBACK_RUN/timing.log"
feedback_exit=$?
set -e
export ARIADNE_CALLER_FEEDBACK_EXIT="$feedback_exit"
python3 - <<'PY'
from pathlib import Path
import hashlib,json,os
root=Path.cwd();out=Path(os.environ['ARIADNE_CALLER_FEEDBACK_RUN'])
manifest=json.loads(Path('/caller-work/source-manifest.json').read_text())
changed=[name for name,identity in manifest['files'].items()
         if hashlib.sha256((root/name).read_bytes()).hexdigest()!=identity]
feedback=json.loads((out/'feedback.json').read_text()) if (out/'feedback.json').exists() else None
record={'exit_code':int(os.environ['ARIADNE_CALLER_FEEDBACK_EXIT']),
        'sources_unchanged':not changed,'changed_sources':changed,
        'feedback_present':feedback is not None,
        'selected_barriers_closed':None if feedback is None else feedback['selected_barriers_closed'],
        'selected_barriers':None if feedback is None else feedback['selected_barriers']}
(out/'run-result.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
if changed:raise SystemExit('source changed during feedback')
PY
exit "$feedback_exit"
