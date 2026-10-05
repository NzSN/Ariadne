#!/usr/bin/env python3
"""Source-bound first-question acceptance; unavailable real Windows stays partial."""
import argparse,hashlib,importlib,json,os,subprocess,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from rust_layout import copy_sut, source_files
from investigation_budget import windows_qualification
from with_mirrorrust_snapshot import active_identity
from investigation_windows_case import CASE_RELATIVE, INSPECTION_RELATIVE, ARCHIVE_RELATIVE, load_case, case_digest
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
 paths=source_files()
 paths.add(ROOT/'tools/with_mirrorrust_snapshot.py')
 paths.update(ROOT/p for p in [CASE_RELATIVE,INSPECTION_RELATIVE,ARCHIVE_RELATIVE,'tools/investigation_windows_case.py'])
 paths.add(ROOT/'tools/test_investigation_windows_case.py')
 for tree in ['src','tests','src/bap','tests/bap','src/input','tests/input','src/reports','tests/reports','src/investigation','tests/investigation','src/bench','native/bap','native/llvm_mc']:
  paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and p.suffix!='.md' and '__pycache__' not in p.parts)
 paths.update(ROOT/p for p in ['Cargo.toml', 'Cargo.lock', 'tools/check_investigation.py', 'tools/check_investigation_mutations.py', 'tools/measure_investigation.py', 'tools/investigation_budget.py', 'tools/test_investigation_budget.py', 'evidence/Ariadne/priority-4-real-capture-case.json', 'tools/check_minidump.py', 'tools/check_minidump_mutations.py', 'tools/check_stage_e.py', 'Specs/Ariadne.tla', 'Specs/AriadneTypes.tla', 'Specs/AriadneMachineCommon.tla'])
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def retained(path, name):
 r=json.loads(path.read_text())
 producer={'mutation':'check_investigation_mutations','workload':'measure_investigation','stage-e':'check_stage_e'}[name]
 if not r.get('passed') or not r.get('sourcesStable') or r.get('sourceHashes')!=importlib.import_module(producer).sources():raise RuntimeError('stale, incomplete or nonpassing retained record: '+str(path))
 return r

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['mutation','workload','stage-e']:p.add_argument('--'+name+'-record',type=Path)
 args=p.parse_args();work=Path(tempfile.mkdtemp(prefix='ariadne-investigation-acceptance-'));before=sources();env={**os.environ,'ARIADNE_LLVM_MC':str(ROOT/'target/ariadne-llvm-mc'),'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')};print('Investigation acceptance artifacts:',work,flush=True)
 gates=[
 ('qualification-regressions',['python3','-m','unittest','discover','-s','tools','-p','test_investigation*.py']),
 ('root-tests',['cargo', 'test', '--no-default-features', '--offline', '--locked']),
 ('root-format',['cargo','fmt','--all','--','--check']),
 ('root-clippy',['cargo', 'clippy', '--no-default-features', '--offline', '--locked', '--all-targets', '--', '-D', 'warnings']),
 ('module-tests',['cargo', 'test', '--no-default-features', '--features', 'investigation', '--offline', '--locked', '--manifest-path', 'Cargo.toml']),
 ('module-format',['cargo', 'fmt', '--manifest-path', 'Cargo.toml', '--', '--check']),
 ('module-clippy',['cargo', 'clippy', '--no-default-features', '--features', 'investigation', '--offline', '--locked', '--manifest-path', 'Cargo.toml', '--all-targets', '--', '-D', 'warnings']),
 ('producer-addresses',['cargo', 'test', '--no-default-features', '--features', 'bap', '--offline', '--locked', '--release', '--manifest-path', 'Cargo.toml', '--test', 'bap_native', 'memory_address_evidence', '--', '--ignored']),
 ('native-cli-questions',['cargo', 'test', '--offline', '--locked', '--release', '--test', 'input_investigation', '--', '--include-ignored']),
 ('input-format',['cargo', 'fmt', '--manifest-path', 'Cargo.toml', '--', '--check']),
 ('input-clippy',['cargo', 'clippy', '--no-default-features', '--features', 'input', '--offline', '--locked', '--manifest-path', 'Cargo.toml', '--all-targets', '--', '-D', 'warnings']),
 ('report-tests',['cargo', 'test', '--no-default-features', '--features', 'reports', '--offline', '--locked', '--manifest-path', 'Cargo.toml']),
 ('report-format',['cargo', 'fmt', '--manifest-path', 'Cargo.toml', '--', '--check']),
 ('report-clippy',['cargo', 'clippy', '--no-default-features', '--features', 'reports', '--offline', '--locked', '--manifest-path', 'Cargo.toml', '--all-targets', '--', '-D', 'warnings']),
 ('mutation',['python3','tools/check_investigation_mutations.py']),
 ('workload',['python3','tools/measure_investigation.py']),
 ('stage-e',['python3','tools/check_stage_e.py']),
 ]
 records=[];nested={}
 for name,command in gates:
  start=time.monotonic();reuse=getattr(args,name.replace('-','_')+'_record',None)
  try:
   if reuse:
    data=retained(reuse,name);nested[name]=data;code=0;output='Reused complete source-hash-verified record: '+str(reuse)+'\n'
    if name=='workload' and any(sha(ROOT/p)!=d for p,d in data['tools'].items()):raise RuntimeError('stale workload binaries')
    if name=='workload' and data.get('qualificationEnvironment')!=active_identity():raise RuntimeError('workload qualification dependency differs')
    if name=='stage-e' and data['tools']['nativeMCSha256']!=sha(ROOT/'target/ariadne-llvm-mc'):raise RuntimeError('stale decoder reference')
    if name=='stage-e' and data.get('qualificationEnvironment')!=active_identity():raise RuntimeError('Stage E qualification dependency differs')
   else:
    r=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True,timeout=1200);code=r.returncode;output=r.stdout+r.stderr
    for line in output.splitlines():
     if line.startswith('Report: '):nested[name]=json.loads(Path(line[8:]).read_text())
   if code==0 and name in ['mutation','workload','stage-e'] and not nested.get(name,{}).get('passed'):raise RuntimeError('missing accepted nested '+name)
  except (OSError,RuntimeError,subprocess.TimeoutExpired) as error:code=-1;output=str(error)
  log=work/f'{name}.log';log.write_text(output);records.append(dict(gate=name,command=['source-hash-check',str(reuse)] if reuse else command,exitCode=code,seconds=round(time.monotonic()-start,3),log=str(log)));print(name,':','PASS' if code==0 else 'FAIL',flush=True)
 stable=before==sources();passed=stable and all(r['exitCode']==0 for r in records)
 active_case=load_case()
 windows=windows_qualification(nested.get('workload',{}),active_case)
 missing=[] if windows['targetMet'] else [windows['reason']]
 if not passed:missing.append('Required implementation/regression gates or source stability did not pass.')
 result=dict(schema='ariadne.investigation-first-delivery/v2',recordedUtc=datetime.now(timezone.utc).isoformat(),passed=passed,sourcesStable=stable,sourceHashes=before,gates=records,records=nested,completionClauses={name:passed for name in ['queryIdentity','bilAddressEvidence','possibleProducerClaims','uncertaintyAndRequirements','strictReportsAndCLI','mutationSensitivity','controlledPlatformCases','retainedLinuxCase','measuredCost']},fullI4RealCaptureAcceptance=passed and windows['targetMet'],windows98Qualification=windows,scope='I0-I3 and I4 exercised tier: both platform fixtures and pinned controlled Linux capture. No historical execution, UAF, complete ISA step or general root-cause proof.',missing=missing,laterI5I7Implemented=False,stage2Qualified=False,tools={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'target/ariadne-bap-lift',ROOT/'target/ariadne-llvm-mc']})
 result['qualificationEnvironment']=active_identity()
 result.update(activeWindowsCaseId=active_case['id'],activeWindowsCaseDigest=case_digest(active_case),originalWindowsCaseExercised=False,scope='I0-I3 and current I4 qualification on fixtures, retained Linux and the active controlled Windows replacement; original Electron capture remains historical. No executed-history, UAF, ISA-step or general root-cause proof.')
 (work/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
