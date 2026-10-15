#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/guard-budget-diagnosis-20261014"
 mkdir -p "$out"
 cp /mnt/d/ariadne-guard-budget-{probe.rs,logging-helper.py,measure.rs,run.sh} "$out/"
 mv "$out/ariadne-guard-budget-probe.rs" "$out/probe.rs"
 mv "$out/ariadne-guard-budget-logging-helper.py" "$out/logging-helper.py"
 mv "$out/ariadne-guard-budget-measure.rs" "$out/measure.rs"
 mv "$out/ariadne-guard-budget-run.sh" "$out/run.sh"
 chmod +x "$out/logging-helper.py"
 chown -R jlc:jlc "$out"
 exec runuser -u jlc -- "$base/run.sh" bash /work/guard-budget-diagnosis-20261014/run.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-bap-shift-count-20261014
export ARIADNE_BAP_CORE_DIR="$PWD/target/shift-native" ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc"
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift" BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
out=/work/guard-budget-diagnosis-20261014
dump=/work/frame-paths-dump03958-20261013/original.dmp
printf '%s\n' "9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab  $dump" | sha256sum --check
python3 - <<'INNER'
from pathlib import Path
import subprocess,os,json,hashlib
root=Path.cwd();out=Path('/work/guard-budget-diagnosis-20261014');build=root/'target/shift-build/release';libs=list((build/'deps').glob('libserde_json-*.rlib'))
paths=['src/input/materialize.rs','src/bap/ast.rs','src/bap/prepare.rs','src/bap/guard_admission.rs','src/investigation/frame_paths.rs','target/shift-build/release/libariadne.rlib','target/ariadne-bap-lift']
manifest={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths};(out/'source-assets.json').write_text(json.dumps(manifest,indent=2)+'\n')
for name in ['probe','measure']:
 subprocess.run(['rustc','--edition=2024',str(out/(name+'.rs')),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libs[0]),'--extern','serde='+str(next((build/'deps').glob('libserde-*.rlib'))),'-o',str(out/name)],check=True,env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
INNER
"$out/probe" "$dump" "$out/baseline" guarded > "$out/baseline.log" 2>&1
export DIAGNOSTIC_REAL_HELPER="$ARIADNE_BAP_HELPER" DIAGNOSTIC_LIFT_LOG="$out/raw-lifts.jsonl"
export ARIADNE_BAP_HELPER="$out/logging-helper.py"
"$out/probe" "$dump" "$out/measured" guarded > "$out/measured.log" 2>&1
cmp "$out/baseline/materialization-progress.json" "$out/measured/materialization-progress.json"
"$out/measure" "$out/raw-lifts.jsonl" "$out/ast-accounting.json"
cat "$out/baseline.log"
cat "$out/measured.log"
python3 - <<'INNER'
from pathlib import Path
import json,collections
out=Path('/work/guard-budget-diagnosis-20261014');j=json.loads((out/'ast-accounting.json').read_text());p=json.loads((out/'measured/materialization-progress.json').read_text());op=collections.defaultdict(lambda:dict(count=0,ast_bytes=0));batch=collections.defaultdict(lambda:dict(count=0,ast_bytes=0))
for r in j['rows']:
 for d,key in [(op,r['opcode']),(batch,r['batch'])]:
  d[key]['count']+=1;d[key]['ast_bytes']+=r['ast_bytes']
summary={k:v for k,v in j.items() if k!='rows'};summary.update({'attempted_starts':len(p['attempted']),'referenced_addresses':len(p['referenced']),'prefix_bytes':p['prefix_bytes'],'completed_decoder_batches':p['completed_decoder_batches'],'progress_equal_baseline':True,'top_sites':sorted(j['rows'],key=lambda r:r['ast_bytes'],reverse=True)[:12],'opcode_costs':sorted([dict(opcode=k,**v) for k,v in op.items()],key=lambda r:r['ast_bytes'],reverse=True),'batch_costs':[dict(batch=k,**v) for k,v in batch.items()]});(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in ('opcode_costs','batch_costs','top_sites')},indent=2));print('largest opcode costs',summary['opcode_costs'][:8]);print('largest sites',summary['top_sites'][:3])
INNER
python3 - <<'INNER'
from pathlib import Path
import tarfile
out=Path('/work/guard-budget-diagnosis-20261014')
with tarfile.open(out/'diagnosis.tar.gz','w:gz') as archive:
 for p in sorted(out.rglob('*')):
  if p.is_file() and p.name not in ['raw-lifts.jsonl','probe','measure','diagnosis.tar.gz']:
   archive.add(p,arcname=str(p.relative_to(out)))
INNER
cp "$out/diagnosis.tar.gz" /mnt/d/ariadne-guard-budget-diagnosis-20261014.tar.gz
