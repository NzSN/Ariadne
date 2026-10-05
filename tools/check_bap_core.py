#!/usr/bin/env python3
"""Qualify the complete native core without conflating candidate and adoption gates."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import check_bap_semantics as stage1
from check_bap_ocaml import tool_identities
from with_mirrorrust_snapshot import active_identity

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sources():
 paths=set()
 for tree in ['src','tests','native','Specs','mbt','tools']:
  paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and p.suffix!='.md'
               and not set(p.parts)&{'target','.work','__pycache__','results','states','_apalache-out'})
 paths.update(ROOT/p for p in ['Cargo.toml','Cargo.lock','docs/Ariadne/bap-analysis-core-design.md','Plans/bap-stage2-implementation.md'])
 paths.update(ROOT/p for p in ['evidence/Ariadne/investigation-windows-workload-case.json','evidence/Ariadne/i4-windows-capture-inspection.json','evidence/Ariadne/bap-windows-workload-inputs.tar.gz'])
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def tools_inventory():
 result=tool_identities()
 for name in ['target/ariadne-bap-lift','target/ariadne-llvm-mc','target/ariadne-llvm-ir','native/bap/toolchain.lock.json','native/bap-core/sdk.lock.json','target/bap-core-sdk/sdk-manifest.json']:
  result[name]=sha(ROOT/name)
 client=ROOT.parent/'MirrorRust'
 result['mirrorrust']={str(p.relative_to(client)):sha(p) for p in [client/'Cargo.toml',*sorted((client/'src').rglob('*.rs'))]}
 result['qualificationEnvironment']=active_identity()
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--candidate',action='store_true',help='qualify explicit native selection, without default-adoption credit')
 parser.add_argument('--stage1-record',type=Path,help='reuse only a complete current source/tool-bound regression record')
 args=parser.parse_args();work=args.output.resolve();work.mkdir(parents=True,exist_ok=True)
 before=sources();tools_before=tools_inventory();gates=[];nested={};artifact_roots=[work]
 helper=ROOT/'target/bap-core-stage2';clean=ROOT/'target/bap-core-stage2-clean'
 env={**os.environ,'ARIADNE_BAP_CORE_DIR':str(helper),'ARIADNE_LLVM_MC':str(ROOT/'target/ariadne-llvm-mc'),
      'ARIADNE_LLVM_IR':str(ROOT/'target/ariadne-llvm-ir'),'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),
      'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable'),'ARIADNE_REPLAY_BACKEND':'rust'}
 graph=ROOT/'tmp/graphviz-headers/root';env.update(ARIADNE_DOT=str(graph/'usr/bin/dot'),GVBINDIR=str(graph/'usr/lib/x86_64-linux-gnu/graphviz'),LD_LIBRARY_PATH=str(graph/'usr/lib/x86_64-linux-gnu'))
 env['ARIADNE_REAL_DUMPS']=str(ROOT.parent/'chromium/src/third_party/breakpad/breakpad/src/processor/testdata')
 env['LLVM20_INCLUDE_DIR']=str(ROOT/'tmp/llvm20-headers/root/usr/include/llvm-20')
 def run(name,command,extra=None,timeout=7200):
  print('Gate:',name,flush=True);start=time.monotonic()
  try:
   r=subprocess.run([str(x) for x in command],cwd=ROOT,env={**env,**(extra or {})},text=True,capture_output=True,timeout=timeout)
   code=r.returncode;output=r.stdout+r.stderr
  except (OSError,subprocess.TimeoutExpired) as e:code=-1;output=str(e)
  (work/f'{name}.log').write_text(output)
  gates.append({'gate':name,'command':[str(x) for x in command],'exitCode':code,'seconds':time.monotonic()-start})
  for line in output.splitlines():
   if line.startswith('Report: '):
    path=Path(line[8:]);record=json.loads(path.read_text());nested[name]=record;artifact_roots.append(path.parent)
  if code:raise RuntimeError(f'{name} failed: {work/name}.log')
  print(name+': PASS',flush=True)
 try:
  run('sdk-inventory',['python3','native/bap-core/setup-sdk.py','--check'])
  run('sdk-smoke',['python3','native/bap-core/check-sdk.py'])
  if clean.exists():shutil.rmtree(clean)
  for name,path in [('helper-build',helper),('helper-clean-build',clean)]:run(name,['python3','native/bap-core/build.py','--output',path])
  if json.loads((helper/'manifest.json').read_text())!=json.loads((clean/'manifest.json').read_text()):raise RuntimeError('clean build identity mismatch')
  run('format',['cargo','fmt','--all','--','--check'])
  run('root-tests',['cargo','test','--offline','--locked'])
  run('core-only-tests',['cargo','test','--offline','--locked','--no-default-features'])
  run('all-feature-clippy',['cargo','clippy','--offline','--locked','--all-features','--all-targets','--','-D','warnings'])
  run('rust-layout',['python3','tools/check_rust_layout.py'])
  run('documentation',['python3','tools/check_doc_links.py'])
  run('contract-regressions',['python3','-m','unittest','discover','-s','tools','-p','test_bap_core_contract.py'])
  run('native-kernels',['cargo','test','--offline','--locked','--test','bap_core_bootstrap','--test','bap_core_analysis','--test','bap_core_stateflow','--','--ignored'])
  run('capture-investigation-cli',['cargo','test','--offline','--locked','--test','input_bap_core','--','--ignored'])
  run('native-stateflow-cli',['cargo','test','--offline','--locked','--test','input_stage_e','--','--ignored'],{'ARIADNE_TEST_ANALYSIS_BACKEND':'bap'})
  run('native-generated-replay',['python3','tools/check_bap_core_replay.py','--output',work/'replay'])
  run('native-algorithm-mutations',['python3','tools/check_bap_core_mutations.py','--output',work/'mutations'])
  run('native-boundary-mutations',['python3','tools/check_bap_ocaml_mutations.py'])
  if args.stage1_record:
   record=stage1.retained(args.stage1_record)
   if record['sourceHashes']!=stage1.sources() or not record['stage1ExitPassed']:raise RuntimeError('incomplete Stage 1 regression reuse')
   if record['records']['stage-e'].get('qualificationEnvironment')!=active_identity():raise RuntimeError('Stage 1 qualification dependency differs')
   stage1.validate_workload_bindings(record['records']['workload'])
   for p,d in record['tools'].items():
    if sha(ROOT/p)!=d:raise RuntimeError('Stage 1 tools changed')
   nested['stage1-regression']=record;artifact_roots.append(args.stage1_record.parent)
   gates.append({'gate':'stage1-regression','command':['verified-record',str(args.stage1_record)],'exitCode':0})
  else:run('stage1-regression',['python3','tools/check_bap_semantics.py'])
  if not nested['stage1-regression'].get('stage1ExitPassed'):raise RuntimeError('Stage 1 regression did not qualify')
  run('release-build',['cargo','build','--offline','--locked','--release','--bin','ariadne-minidump'])
  run('native-product-workloads',['python3','tools/check_bap_core_product.py','--output',work/'product',*([] if args.candidate else ['--expect-default'])])
  for key,path in [('generatedReplay','replay/result.json'),('algorithmMutations','mutations/result.json'),('productWorkloads','product/result.json')]:
   nested[key]=json.loads((work/path).read_text())
   if not nested[key]['passed']:raise RuntimeError(key+' missing pass')
  if sources()!=before or tools_inventory()!=tools_before:raise RuntimeError('source/tool identity changed during qualification')
  passed=True;error=None
 except Exception as e:
  passed=False;error=str(e);print(error,flush=True)
 result={'schema':'ariadne.bap-core-qualification/v1','recordedUtc':datetime.now(timezone.utc).isoformat(),
         'passed':passed,'stage2Qualified':passed and not args.candidate,'defaultNativeVerified':passed and not args.candidate,
         'candidateOnly':args.candidate,'sourceHashes':before,'tools':tools_before,'sourcesStable':sources()==before,
         'gates':gates,'records':nested,'error':error,'scope':'native fixed-input recovery/dataflow/slice and supplied finite stateflow; capture-only product integration; BAP lifting trusted; supplied LLVM IR remains a separate Rust path; no universal refinement or ISA proof'}
 (work/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 if not passed:raise SystemExit(1)
 archive=work/'evidence.tar.gz';entries={}
 with tarfile.open(archive,'w:gz') as tar:
  def add(path,name):
   if name in entries:return
   entries[name]=sha(path);tar.add(path,arcname=name,recursive=False)
  for p in before:add(ROOT/p,'sources/'+p)
  for filename in ['ariadne-bap-core','manifest.json','build.log']:add(helper/filename,'helper/'+filename)
  if tools_before['qualificationEnvironment']:
   add(Path(tools_before['qualificationEnvironment']['manifestPath']),'dependencies/mirrorrust-snapshot.json')
  for index,directory in enumerate(dict.fromkeys(artifact_roots)):
   for p in sorted(directory.rglob('*')):
    if p.is_file() and p!=archive and not set(p.parts)&{'rust-build','debug','release','__pycache__'} and (p.suffix in ['.json','.log','.diff','.ml','.txt','.dot','.csv','.stderr','.stdout','.time'] or p.name=='ariadne-bap-core'):
     add(p,f'artifacts/{index}/'+str(p.relative_to(directory)))
 with tarfile.open(archive,'r:gz') as tar:
  actual={m.name:hashlib.sha256(tar.extractfile(m).read()).hexdigest() for m in tar.getmembers() if m.isfile()}
 if actual!=entries:raise RuntimeError('archive verification failed')
 manifest={'schema':'ariadne.bap-core-evidence/v1','archiveSha256':sha(archive),'entries':entries,'verified':True,'qualificationReportSha256':sha(work/'report.json')}
 (work/'evidence-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('Verified archive:',archive,flush=True)
if __name__=='__main__':main()
