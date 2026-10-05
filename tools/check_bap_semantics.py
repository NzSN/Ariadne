#!/usr/bin/env python3
"""Source-bound BAP-only removal validation, with separate Stage 1 qualification."""
import argparse,hashlib,json,os,subprocess,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from rust_layout import copy_sut, source_files
from bap_workload_contract import windows_qualification
from with_mirrorrust_snapshot import active_identity
from measure_bap import WINDOWS_ARCHIVE_RELATIVE, WINDOWS_CASE_PATH, sources as workload_sources
ROOT=Path(__file__).resolve().parents[1]
WORKLOAD_TOOLS=('target/release/ariadne-minidump','target/release/bap_minidump','target/ariadne-llvm-mc','target/ariadne-bap-lift','native/bap/toolchain.lock.json','tools/measure_bap.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
 paths=source_files()
 paths.add(ROOT/'tools/with_mirrorrust_snapshot.py')
 for tree in ['src','tests','src/input','tests/input','src/examples','src/reports','tests/reports','src/bap','src/investigation','tests/bap','src/bench','native/llvm_mc','native/bap']:
  paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.md')
 paths.update(ROOT/p for p in ['Cargo.toml','Cargo.lock','Cargo.toml','Cargo.lock','Cargo.toml','Cargo.lock','Cargo.toml','Cargo.lock','Cargo.toml','Cargo.lock','Cargo.toml','Cargo.lock','Specs/Ariadne.tla','Specs/AriadneMachineCommon.tla','Specs/AriadneTypes.tla','tools/check_bap_semantics.py','tools/check_bap_model.py','tools/check_bap_mutations.py','tools/measure_bap.py','tools/test_bap_workload.py','tools/bap_workload_contract.py','tools/test_bap_workload_contract.py','tools/test_bap_workload_gate.py','tools/check_stage_e.py','tools/check_minidump.py','tools/check_minidump_mutations.py'])
 paths.update(ROOT/p for p in ['evidence/Ariadne/priority-1-real-capture-case.json','evidence/Ariadne/bap-windows-workload-case.json',WINDOWS_ARCHIVE_RELATIVE])
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def validate_workload_bindings(data):
 if not isinstance(data,dict) or data.get('passed') is not True or data.get('sourcesStable') is not True:raise RuntimeError('workload record must pass with stable sources')
 if data.get('sourceHashes')!=workload_sources():raise RuntimeError('workload source inventory is incomplete or stale')
 if data.get('tools')!={p:sha(ROOT/p) for p in WORKLOAD_TOOLS}:raise RuntimeError('workload tool inventory is incomplete or stale')
def retained(path,hashkey='sourceHashes'):
 data=json.loads(path.read_text())
 if not data.get('passed') or not data.get('sourcesStable') or not data.get(hashkey) or any(sha(ROOT/p)!=d for p,d in data[hashkey].items()):raise RuntimeError(f'stale or nonpassing retained record: {path}')
 return data

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['stage-e','model','mutation','workload']:p.add_argument('--'+name+'-record',type=Path)
 args=p.parse_args();work=Path(tempfile.mkdtemp(prefix='ariadne-bap-acceptance-'));before=sources();env={**os.environ,'ARIADNE_LLVM_MC':str(ROOT/'target/ariadne-llvm-mc'),'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
 graph=ROOT/'tmp/graphviz-headers/root'
 if 'ARIADNE_DOT' not in env and (graph/'usr/bin/dot').is_file():
  env['ARIADNE_DOT']=str(graph/'usr/bin/dot');env['GVBINDIR']=str(graph/'usr/lib/x86_64-linux-gnu/graphviz')
  env['LD_LIBRARY_PATH']=str(graph/'usr/lib/x86_64-linux-gnu')+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
 nested={};results=[];print('BAP acceptance artifacts:',work,flush=True)
 gates=[
 ('workload-runner-regressions',['python3','-m','unittest','discover','-s','tools','-p','test_bap_workload*.py']),
 ('native-build',['bash','native/bap/build.sh']),
 ('native-corpus',['python3','tests/bap/fixtures/make_corpus.py','--check']),
 ('controlled-fixtures',['python3','tests/input/fixtures/make_bap.py','--check']),
 ('bap-format',['cargo', 'fmt', '--manifest-path', 'Cargo.toml', '--', '--check']),
 ('bap-clippy',['cargo', 'clippy', '--no-default-features', '--features', 'bap', '--offline', '--locked', '--manifest-path', 'Cargo.toml', '--all-targets', '--', '-D', 'warnings']),
 ('bap-tests-native',['cargo', 'test', '--no-default-features', '--features', 'bap', '--offline', '--locked', '--release', '--manifest-path', 'Cargo.toml', '--', '--include-ignored']),
 ('input-format',['cargo', 'fmt', '--manifest-path', 'Cargo.toml', '--', '--check']),
 ('input-clippy',['cargo', 'clippy', '--no-default-features', '--features', 'input', '--offline', '--locked', '--manifest-path', 'Cargo.toml', '--all-targets', '--', '-D', 'warnings']),
 ('input-bap-cli',['cargo', 'test', '--offline', '--locked', '--release', '--test', 'input_bap_backend', '--', '--include-ignored']),
 ('bench-format',['cargo', 'fmt', '--manifest-path', 'Cargo.toml', '--', '--check']),
 ('bench-clippy',['cargo', 'clippy', '--no-default-features', '--features', 'bench', '--offline', '--locked', '--manifest-path', 'Cargo.toml', '--all-targets', '--', '-D', 'warnings']),
 ('model-observer-build',['cargo', 'build', '--no-default-features', '--features', 'validation', '--offline', '--locked', '--release', '--manifest-path', 'Cargo.toml', '--bin', 'bap-model-case']),
 ('model',['python3','tools/check_bap_model.py']),
 ('mutation',['python3','tools/check_bap_mutations.py']),
 ('workload',['python3','tools/measure_bap.py']),
 ('stage-e',['python3','tools/check_stage_e.py']),
 ]
 for name,cmd in gates:
  start=time.monotonic();reuse=getattr(args,name.replace('-','_')+'_record',None)
  try:
   if reuse:
    if name=='workload':
     data=json.loads(reuse.read_text());validate_workload_bindings(data)
    else:data=retained(reuse)
    nested[name]=data;output=f'Reused exact source-hash-verified record: {reuse}\n';code=0
    if name=='model' and data['observerSha256']!=sha(ROOT/'target/release/bap-model-case'):raise RuntimeError('model observer binary changed')
    if name=='stage-e' and (data['tools']['nativeMCSha256']!=sha(ROOT/'target/ariadne-llvm-mc') or data['tools']['nativeIRSha256']!=sha(ROOT/'target/ariadne-llvm-ir')):raise RuntimeError('Stage E native tools changed')
    if name=='stage-e' and data.get('qualificationEnvironment')!=active_identity():raise RuntimeError('Stage E qualification dependency differs')
   else:
    r=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=1200);code=r.returncode;output=r.stdout+r.stderr
    for line in output.splitlines():
     if line.startswith('Report: '):nested[name]=json.loads(Path(line[8:]).read_text())
   if code==0 and name in ['model','mutation','workload','stage-e'] and not nested.get(name,{}).get('passed'):raise RuntimeError(f'{name}: missing passing nested record')
   if code==0 and name=='workload':validate_workload_bindings(nested[name])
  except (RuntimeError,subprocess.TimeoutExpired,OSError) as error:code=-1;output=str(error)
  log=work/f'{name}.log';log.write_text(output);results.append(dict(gate=name,command=['source-hash-check',str(reuse)] if reuse else cmd,exitCode=code,seconds=round(time.monotonic()-start,3),log=str(log)))
  print(name,':','PASS' if code==0 else 'FAIL',flush=True)
 stable=before==sources();implemented=stable and all(r['exitCode']==0 for r in results)
 measured=nested.get('workload',{})
 windows=windows_qualification(measured,json.loads(WINDOWS_CASE_PATH.read_text()))
 full_stage1=implemented and windows['targetMet']
 missing=[] if windows['targetMet'] else ['S4/S5: '+windows['reason']]
 if not implemented:missing.append('Required implementation/regression gates or source stability did not pass.')
 record=dict(schema='ariadne.bap-only-removal/v5',recordedUtc=datetime.now(timezone.utc).isoformat(),passed=implemented,implementationGatesPassed=implemented,stage1ExitPassed=full_stage1,sourcesStable=stable,sourceHashes=before,gates=results,records=nested,tools={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'target/ariadne-bap-lift',ROOT/'target/ariadne-llvm-mc',ROOT/'native/bap/toolchain.lock.json']},selectedToolchain=json.loads((ROOT/'native/bap/toolchain.lock.json').read_text()),nativeCorpusCases=41,admittedOpcodeForms=30,semanticBackend="bap-only",llvmSemanticSelector=False,llvmSemanticFallback=False,llvmRole="independent decoded-fact reference; separate supplied-IR path remains",defaultSelectionAuthorizedBy="explicit user instruction to remove LLVM semantic backend",instructionStepTrack='retired; BAP lifting is a trusted dependency',stage2Started=False,stage2Qualified=False,stage2PrerequisiteSatisfied=full_stage1,defaultPromotionEligible=full_stage1,windowsWorkloadQualification=windows,qualificationPolicy='Full Stage 1 exit and the Stage 2 prerequisite require valid pinned controlled Windows evidence under the user-authorized unlimited timing policy; latency is measured but does not gate acceptance; existing default selection remains separately authorized.',missing=missing,scope='Sole BAP minidump semantic producer into the existing Rust core; finite tested projection and model-relative solver conformance, no ISA-step proof or BAP-owned analysis core')
 if env.get('ARIADNE_DOT') and Path(env['ARIADNE_DOT']).is_file():record['graphviz']={'path':env['ARIADNE_DOT'],'sha256':sha(env['ARIADNE_DOT'])}
 record['qualificationEnvironment']=active_identity()
 (work/'report.json').write_text(json.dumps(record,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 raise SystemExit(0 if record['passed'] else 1)
if __name__=='__main__':main()
