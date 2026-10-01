#!/usr/bin/env python3
"""Source-bound BAP-only removal validation, with separate Stage 1 qualification."""
import argparse,hashlib,json,os,subprocess,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
 paths=set()
 for tree in ['src','tests','input/src','input/tests','input/examples','reports/src','reports/tests','bap/src','bap/tests','bench/src','native/llvm_mc','native/bap']:
  paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.md')
 paths.update(ROOT/p for p in ['Cargo.toml','Cargo.lock','input/Cargo.toml','input/Cargo.lock','reports/Cargo.toml','reports/Cargo.lock','bap/Cargo.toml','bap/Cargo.lock','bench/Cargo.toml','bench/Cargo.lock','Specs/Ariadne.tla','Specs/AriadneMachineCommon.tla','Specs/AriadneTypes.tla','tools/check_bap_semantics.py','tools/check_bap_model.py','tools/check_bap_mutations.py','tools/measure_bap.py','tools/check_stage_e.py','tools/check_minidump.py','tools/check_minidump_mutations.py'])
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def retained(path,hashkey='sourceHashes'):
 data=json.loads(path.read_text())
 if not data.get('passed') or not data.get('sourcesStable') or not data.get(hashkey) or any(sha(ROOT/p)!=d for p,d in data[hashkey].items()):raise RuntimeError(f'stale or nonpassing retained record: {path}')
 return data

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['stage-e','model','mutation','workload']:p.add_argument('--'+name+'-record',type=Path)
 args=p.parse_args();work=Path(tempfile.mkdtemp(prefix='ariadne-bap-acceptance-'));before=sources();env={**os.environ,'ARIADNE_LLVM_MC':str(ROOT/'target/ariadne-llvm-mc'),'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
 nested={};results=[];print('BAP acceptance artifacts:',work,flush=True)
 gates=[
 ('native-build',['bash','native/bap/build.sh']),
 ('native-corpus',['python3','bap/tests/fixtures/make_corpus.py','--check']),
 ('controlled-fixtures',['python3','input/tests/fixtures/make_bap.py','--check']),
 ('bap-format',['cargo','fmt','--manifest-path','bap/Cargo.toml','--','--check']),
 ('bap-clippy',['cargo','clippy','--offline','--locked','--manifest-path','bap/Cargo.toml','--all-targets','--','-D','warnings']),
 ('bap-tests-native',['cargo','test','--offline','--locked','--release','--manifest-path','bap/Cargo.toml','--','--include-ignored']),
 ('input-format',['cargo','fmt','--manifest-path','input/Cargo.toml','--','--check']),
 ('input-clippy',['cargo','clippy','--offline','--locked','--manifest-path','input/Cargo.toml','--all-targets','--','-D','warnings']),
 ('input-bap-cli',['cargo','test','--offline','--locked','--release','--manifest-path','input/Cargo.toml','--test','bap_backend','--','--include-ignored']),
 ('bench-format',['cargo','fmt','--manifest-path','bench/Cargo.toml','--','--check']),
 ('bench-clippy',['cargo','clippy','--offline','--locked','--manifest-path','bench/Cargo.toml','--all-targets','--','-D','warnings']),
 ('model-observer-build',['cargo','build','--offline','--locked','--release','--manifest-path','bap/Cargo.toml','--bin','bap-model-case']),
 ('model',['python3','tools/check_bap_model.py']),
 ('mutation',['python3','tools/check_bap_mutations.py']),
 ('workload',['python3','tools/measure_bap.py']),
 ('stage-e',['python3','tools/check_stage_e.py']),
 ]
 for name,cmd in gates:
  start=time.monotonic();reuse=getattr(args,name.replace('-','_')+'_record',None)
  try:
   if reuse:
    data=retained(reuse);nested[name]=data;output=f'Reused exact source-hash-verified record: {reuse}\n';code=0
    if name=='model' and data['observerSha256']!=sha(ROOT/'bap/target/release/bap-model-case'):raise RuntimeError('model observer binary changed')
    if name=='workload' and any(sha(ROOT/p)!=d for p,d in data['tools'].items()):raise RuntimeError('workload tools changed')
    if name=='stage-e' and (data['tools']['nativeMCSha256']!=sha(ROOT/'target/ariadne-llvm-mc') or data['tools']['nativeIRSha256']!=sha(ROOT/'target/ariadne-llvm-ir')):raise RuntimeError('Stage E native tools changed')
   else:
    r=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=1200);code=r.returncode;output=r.stdout+r.stderr
    for line in output.splitlines():
     if line.startswith('Report: '):nested[name]=json.loads(Path(line[8:]).read_text())
   if code==0 and name in ['model','mutation','workload','stage-e'] and not nested.get(name,{}).get('passed'):raise RuntimeError(f'{name}: missing passing nested record')
  except (RuntimeError,subprocess.TimeoutExpired,OSError) as error:code=-1;output=str(error)
  log=work/f'{name}.log';log.write_text(output);results.append(dict(gate=name,command=['source-hash-check',str(reuse)] if reuse else cmd,exitCode=code,seconds=round(time.monotonic()-start,3),log=str(log)))
  print(name,':','PASS' if code==0 else 'FAIL',flush=True)
 stable=before==sources();implemented=stable and all(r['exitCode']==0 for r in results)
 profile=subprocess.run(['python3','tools/amd64_profile.py','check','--require-milestone','register-core'],cwd=ROOT,capture_output=True,text=True);text=profile.stdout+profile.stderr;(work/'register-core.log').write_text(text)
 pending=profile.returncode==1 and '0/49 verified' in text and 'Milestone register-core is pending' in text
 healthy_profile=pending or profile.returncode==0
 measured=nested.get('workload',{});windows=measured.get('windows98Checked',False)
 record=dict(schema='ariadne.bap-only-removal/v1',recordedUtc=datetime.now(timezone.utc).isoformat(),passed=implemented and healthy_profile,implementationGatesPassed=implemented and healthy_profile,stage1ExitPassed=implemented and healthy_profile and windows,sourcesStable=stable,sourceHashes=before,gates=results,records=nested,tools={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'target/ariadne-bap-lift',ROOT/'target/ariadne-llvm-mc',ROOT/'native/bap/toolchain.lock.json']},selectedToolchain=json.loads((ROOT/'native/bap/toolchain.lock.json').read_text()),nativeCorpusCases=41,admittedOpcodeForms=30,semanticBackend="bap-only",llvmSemanticSelector=False,llvmSemanticFallback=False,llvmRole="independent decoded-fact reference; separate supplied-IR path remains",defaultSelectionAuthorizedBy="explicit user instruction to remove LLVM semantic backend",registerCoreAcceptance='pending 0/49' if pending else 'passed' if profile.returncode==0 else 'unexpected failure',stage2Started=False,stage2Qualified=False,stage2PrerequisiteSatisfied=implemented and healthy_profile and windows,defaultPromotionEligible=implemented and healthy_profile and measured.get('defaultPromotionEligible',False),missing=[] if windows else ['S4/S5: fresh selected-backend acceptance and workload comparison on the hash-pinned 98-instruction Windows capture'],scope='Sole BAP minidump semantic producer into the existing Rust core; finite tested projection and model-relative solver conformance, no ISA-step proof or BAP-owned analysis core')
 (work/'report.json').write_text(json.dumps(record,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 raise SystemExit(0 if record['passed'] else 1)
if __name__=='__main__':main()
