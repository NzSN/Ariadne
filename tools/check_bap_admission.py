#!/usr/bin/env python3
"""Source-frozen P4 qualification; external Electron acceptance stays a separate tier."""
import argparse,hashlib,json,os,shutil,subprocess,tarfile,time
from datetime import datetime,timezone
from pathlib import Path
import check_bap_core
from with_mirrorrust_snapshot import active_identity
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
 before=check_bap_core.sources();identity=active_identity()
 if identity is None:raise SystemExit('sealed dependency snapshot required')
 env={**os.environ,'ARIADNE_BAP_CORE_DIR':str(ROOT/'target/bap-core-native'),'ARIADNE_LLVM_MC':str(ROOT/'target/ariadne-llvm-mc'),'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
 graph=ROOT/'tmp/graphviz-headers/root';env.update(ARIADNE_DOT=str(graph/'usr/bin/dot'),GVBINDIR=str(graph/'usr/lib/x86_64-linux-gnu/graphviz'),LD_LIBRARY_PATH=str(graph/'usr/lib/x86_64-linux-gnu'))
 env['ARIADNE_REAL_DUMPS']=str(ROOT.parent/'chromium/src/third_party/breakpad/breakpad/src/processor/testdata')
 env['LLVM20_INCLUDE_DIR']=str(ROOT/'tmp/llvm20-headers/root/usr/include/llvm-20')
 gates=[];nested={};artifact_roots=[out]
 def run(name,command,timeout=14400):
  print('Gate:',name,flush=True);start=time.monotonic();result=subprocess.run([str(x) for x in command],cwd=ROOT,env=env,text=True,capture_output=True,timeout=timeout)
  text=result.stdout+result.stderr;(out/(name+'.log')).write_text(text);gates.append(dict(gate=name,command=[str(x) for x in command],exitCode=result.returncode,seconds=time.monotonic()-start))
  for line in text.splitlines():
   if line.startswith('Report: '):
    p=Path(line[8:]);nested[name]=json.loads(p.read_text());artifact_roots.append(p.parent)
  if result.returncode:raise RuntimeError(name+' failed: '+str(out/(name+'.log')))
  print(name,': PASS',flush=True)
 passed=False;error=None
 try:
  run('independent-contract',['python3','tests/bap/fixtures/admission/oracle.py','--check'])
  run('owned-fixtures',['python3','tests/input/fixtures/make_admission.py','--check'])
  run('numeric-producer-oracle',['python3','tools/check_bap_admission_oracle.py','--output',out/'scalar-oracle.json'])
  run('profile-migration-controls',['python3','-m','unittest','discover','-s','tools','-p','test_bap_profile_migration.py'])
  run('native-core-stage1-stage-e',['python3','tools/check_bap_core.py','--output',out/'native-core'])
  core=nested['native-core-stage1-stage-e']
  if not core.get('stage2Qualified') or not core.get('defaultNativeVerified'):raise RuntimeError('native default tier not qualified')
  run('profile-migration',['python3','tools/compare_i5a_cli.py'])
  run('native-i5-corpus',['cargo','test','--offline','--locked','--release','--test','input_i5a','--test','input_i5b','--','--include-ignored'])
  run('i5a-fixed-budgets',['python3','tools/measure_i5a.py'])
  run('i4-fixed-budgets',['python3','tools/measure_investigation.py'])
  i4=nested['i4-fixed-budgets']
  if not i4.get('explanationPhaseBudgetMet') or not i4.get('windows98Qualification',{}).get('targetMet'):
   raise RuntimeError('unchanged I4 phase/CLI budgets not met')
  run('owned-capture-workloads',['python3','tools/measure_bap_admission.py','--output',out/'owned-workloads'])
  if before!=check_bap_core.sources():raise RuntimeError('source inventory changed during campaign')
  if core['records']['productWorkloads']['executableSha256']!=sha(ROOT/'target/release/ariadne-minidump'):raise RuntimeError('normal release executable changed after native qualification')
  if not all(r.get('passed') for r in nested.values()):raise RuntimeError('required nested record is not passing')
  passed=True
 except Exception as failure:error=str(failure);print(error,flush=True)
 external=dict(exercised=False,qualified=False,requiredArtifactSha256='9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab',thread='0x5c74',reason='external original/scoped derivative and Scanner/PreParser root/query witness not available; path requested')
 core=nested.get('native-core-stage1-stage-e',{})
 report=dict(schema='ariadne.bap-admission-qualification/v1',recordedUtc=datetime.now(timezone.utc).isoformat(),passed=passed,sourceFixtureTierQualified=passed,rustReleaseRuntimeTierQualified=passed,nativeDefaultTierQualified=passed,externalCaptureTier=external,fullPlanAcceptance=False,sourcesStable=before==check_bap_core.sources(),sourceHashes=before,qualificationEnvironment=identity,gates=gates,records=nested,error=error,projection='bap-bit-provenance-v3',scope='finite v3 projection/normal-continuation and native/model/mutation/owned-capture qualification; external Electron tier separate, no root-cause or universal ISA/refinement proof')
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Report:',out/'report.json',flush=True)
 if not passed:raise SystemExit(1)
 archive=out/'evidence.tar.gz';entries={}
 with tarfile.open(archive,'w:gz') as tar:
  def add(p,name):
   if name in entries:return
   entries[name]=sha(p);tar.add(p,arcname=name,recursive=False)
  for p in before:add(ROOT/p,'sources/'+p)
  for p in (ROOT/'evidence/Ariadne/bap-admission').rglob('*'):
   if p.is_file():add(p,'p0-p3/'+str(p.relative_to(ROOT/'evidence/Ariadne/bap-admission')))
  for i,directory in enumerate(dict.fromkeys(artifact_roots)):
   for p in sorted(directory.rglob('*')):
    if p.is_file() and p!=archive and '__pycache__' not in p.parts and p.suffix in ['.json','.log','.txt','.dot','.csv','.diff','.gz','.ml','.stderr','.stdout','.time']:
     add(p,f'artifacts/{i}/'+str(p.relative_to(directory)))
  add(Path(identity['manifestPath']),'dependencies/mirrorrust-snapshot.json')
 actual={}
 with tarfile.open(archive,'r|gz') as tar:
  for m in tar:
   if not m.isfile():continue
   actual[m.name]=hashlib.sha256(tar.extractfile(m).read()).hexdigest()
 if actual!=entries:raise RuntimeError('archive member verification failed')
 manifest=dict(schema='ariadne.bap-admission-evidence/v1',verified=True,archiveSha256=sha(archive),qualificationReportSha256=sha(out/'report.json'),entries=entries)
 (out/'evidence-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Verified archive:',archive,flush=True)
if __name__=='__main__':main()
