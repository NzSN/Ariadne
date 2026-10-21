#!/usr/bin/env bash
# W0 question-model/oracle tier. Run heavy model commands on the qualification host.
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $# -gt 1 ]]; then
  printf 'Usage: bash Specs/check-address-wrap.sh [NEW_RESULT_DIRECTORY]\n' >&2
  exit 2
fi
if [[ $# -eq 1 ]]; then
  result_root=$(realpath -m -- "$1")
  if [[ -e "$result_root" ]]; then
    printf 'Refusing an existing result directory: %s\n' "$result_root" >&2
    exit 2
  fi
  mkdir -p "$result_root"
else
  result_root=$(mktemp -d "${TMPDIR:-/tmp}/ariadne-i5c-model.XXXXXXXX")
fi
printf 'I5c W0 results: %s\n' "$result_root"
python3 -B - "$repo_root" "$result_root" <<'PY'
import hashlib,json,os,platform,re,shutil,subprocess,sys
from pathlib import Path
root,output=map(Path,sys.argv[1:])
def sha(path):
 h=hashlib.sha256()
 with path.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
model_names=['AriadneAddressWrap.tla','AriadneAddressWrapCases.tla','AddressWrap.cfg','AddressWrapArithmetic.cfg','AddressWrapAdmission.cfg','AddressWrapBudgets.cfg','AddressWrapForms.cfg','AddressWrapPayload.cfg','check-address-wrap.sh']
names=['Specs/'+n for n in model_names]
names+=['tests/input/fixtures/make_i5c.py','tests/input/test_i5c_oracle.py','tests/input/test_i5c_repeat.py','tools/check_i5c_model_inputs.py','tools/check_i5c_model_projection.py','tests/investigation/fixtures/address_wrap_integer.rs']
names+=['tests/input/fixtures/i5c/'+n for n in ['manifest.json','qualification-matrix.json','mutations.json','performance.json','owned-captures.json','model-cases.json','raw-corpus.json','producer-selection-facts.json']]
binding=json.loads((root/'tests/input/fixtures/i5c/producer-selection-facts.json').read_text())
fixture=json.loads((root/'tests/input/fixtures/i5c/manifest.json').read_text())
by_name={row['name']:row for row in fixture['cases']}
assert binding['schema']=='ariadne.i5c-v4-producer-selection-binding/v1'
assert binding['producer_cases']==114
assert set(binding['changed_cases'])=={'operand-size','vector','repeat','lock'}
for name,selected in binding['changed_cases'].items():
 assert by_name[name]['selected_instruction']==selected,name
 assert by_name[name]['receipt'] is False and selected['receipt_present'] is False
corpus=json.loads((root/'tests/input/fixtures/i5c/raw-corpus.json').read_text())
assert corpus['schema']=='ariadne.i5c-raw-fixture-corpus/v1'
assert corpus['case_count']==len(corpus['cases'])==114
assert corpus['required_before_W1'] is True
raw_root=root/'tests/input/fixtures/i5c/dumps'
if not raw_root.is_dir():
 raise SystemExit('Materialize the 114 raw inputs remotely first: python3 -B tests/input/fixtures/make_i5c.py --check --dump-output tests/input/fixtures/i5c/dumps')
case_names=[row['name'] for row in corpus['cases']]
assert len(set(case_names))==114
assert all(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name)for name in case_names)
assert {path.name for path in raw_root.iterdir()}=={name+'.dmp'for name in case_names}|{'manifest.json'}
assert json.loads((raw_root/'manifest.json').read_text())['cases']==corpus['cases']
for row in corpus['cases']:
 path=raw_root/(row['name']+'.dmp')
 assert path.is_file()and not path.is_symlink()
 assert path.stat().st_size==row['bytes']and sha(path)==row['sha256'],row['name']
names+=['tests/input/fixtures/i5c/dumps/'+name+'.dmp'for name in case_names]
names+=['tests/input/fixtures/i5c/dumps/manifest.json']
sources={n:sha(root/n)for n in names}
commands={name:os.environ.get(variable,name)for name,variable in [('apalache-mc','APALACHE_MC'),('tlc','TLC')]}
commands.update({'java':'java','python3':'python3'})
tools={name:Path(shutil.which(command)).resolve()for name,command in commands.items()}
def selected_jar(name,variable):
 if os.environ.get(variable):
  path=Path(os.environ[variable]).resolve()
  assert path.is_file(),f'{variable} must name the actual selected JAR'
  return path
 with tools[name].open('rb')as f:text=f.read(1024*1024).decode('utf-8',errors='ignore')
 candidates={Path(value).resolve()for value in re.findall(r'''(/[^\s:'";]+\.jar)''',text)}
 candidates={path for path in candidates if path.is_file()}
 assert len(candidates)==1,f'Set {variable} to bind the selected runtime JAR; launcher discovery is ambiguous'
 return next(iter(candidates))
tools['apalache_jar']=selected_jar('apalache-mc','APALACHE_JAR')
tools['tlc_jar']=selected_jar('tlc','TLC_JAR')
identity={name:{'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size}for name,path in tools.items()}
versions={name:subprocess.check_output(command,text=True,stderr=subprocess.STDOUT)for name,command in [('java',[commands['java'],'-version']),('apalache',[commands['apalache-mc'],'version']),('python',[commands['python3'],'--version'])]}
(output/'inputs.json').write_text(json.dumps({'source_sha256':sources,'tools':identity,'versions':versions,'platform':platform.platform()},indent=2)+'\n')
PY
python3 -B "$repo_root/tests/input/fixtures/make_i5c.py" --check > "$result_root/oracle.log" 2>&1
python3 -B "$repo_root/tests/input/test_i5c_oracle.py" > "$result_root/oracle-controls.log" 2>&1
python3 -B "$repo_root/tools/check_i5c_model_inputs.py" --check > "$result_root/model-inputs.log" 2>&1
python3 -B "$repo_root/tools/check_i5c_model_projection.py" --output "$result_root/model-input-crosscheck.json" > "$result_root/model-input-crosscheck.log" 2>&1
python3 -B "$repo_root/tests/input/test_i5c_repeat.py" --output "$result_root/repeat-equivalence.json" > "$result_root/repeat-equivalence.log" 2>&1
cd "$repo_root/Specs"
"${APALACHE_MC:-apalache-mc}" --out-dir="$result_root/typecheck" typecheck AriadneAddressWrap.tla > "$result_root/typecheck.log" 2>&1
for config in AddressWrap AddressWrapArithmetic AddressWrapAdmission AddressWrapBudgets AddressWrapForms AddressWrapPayload; do
  "${TLC:-tlc}" -workers 1 -metadir "$result_root/$config" -config "$config.cfg" AriadneAddressWrap.tla > "$result_root/$config.log" 2>&1
done
python3 -B - "$repo_root" "$result_root" <<'PY'
import hashlib,json,sys
from pathlib import Path
root,output=map(Path,sys.argv[1:])
def sha(path):
 h=hashlib.sha256()
 with path.open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
before=json.loads((output/'inputs.json').read_text())
assert all(sha(root/name)==digest for name,digest in before['source_sha256'].items()),'W0 sources changed during checks'
assert all(sha(Path(value['path']))==value['sha256']for value in before['tools'].values()),'W0 tools changed during checks'
corpus=json.loads((root/'tests/input/fixtures/i5c/raw-corpus.json').read_text())
raw_root=root/'tests/input/fixtures/i5c/dumps'
assert {path.name for path in raw_root.iterdir()}=={row['name']+'.dmp'for row in corpus['cases']}|{'manifest.json'},'raw corpus members changed'
assert json.loads((raw_root/'manifest.json').read_text())['cases']==corpus['cases'],'raw corpus manifest changed'
assert all((raw_root/(row['name']+'.dmp')).is_file()and not(raw_root/(row['name']+'.dmp')).is_symlink()for row in corpus['cases']),'raw corpus file kind changed'
logs={p.name:sha(p)for p in sorted(output.glob('*.log'))}
record={'schema':'ariadne.i5c-w0-check/v1','passed':True,'decision_oracle_cases':140,
        'model_scenarios':52,'typechecks':1,'tlc_configurations':6,'repeat_equivalence_cases':88,
        'raw_synthetic_input_count':114,'raw_corpus_materialized':True,'raw_corpus_inventory_stable':True,
        'producer_preparation_exercised':False,
        'source_stable':True,'tools_stable':True,'source_sha256':before['source_sha256'],
        'tools':before['tools'],'tool_versions':before['versions'],'log_sha256':logs,
        'apalache_bounded_smt_claimed':False,'runtime_implementation_exercised':False,
        'owned_capture_exercised':False,'sourceFixtureAcceptance':False,
        'controlledWindowsPartialAcceptance':False,'controlledWindowsFullAcceptance':False,'fullI5cAcceptance':False,
        'scope':'W0 question-level model and independent expectations only; implementation conformance and W1-W5 acceptance are separate.'}
(output/'report.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
PY
