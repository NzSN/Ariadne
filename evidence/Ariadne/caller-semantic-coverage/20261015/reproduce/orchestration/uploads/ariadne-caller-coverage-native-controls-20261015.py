from pathlib import Path
import concurrent.futures,hashlib,json,os,subprocess,time
root=Path('/home/nzsn/Repos/Ariadne-caller-coverage-20261015');os.chdir(root)
out=Path('/caller-work/evidence')/('native-controls-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir();print('Early artifacts:',out,flush=True)
env={**os.environ,'CARGO_TARGET_DIR':str(root/'target/caller-build'),'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','CARGO_BUILD_JOBS':'4','ARIADNE_BAP_HELPER':str(root/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(root/'tmp/bap-setup/stable'),'ARIADNE_LLVM_MC':str(root/'target/caller-llvm/ariadne-llvm-mc'),'ARIADNE_BAP_CORE_DIR':str(root/'target/caller-native'),'ARIADNE_LEGACY_COMPOSED_MINIDUMP':'/caller-work/legacy/v1-minidump.json','ARIADNE_LEGACY_COMPOSED_FRAME':'/caller-work/legacy/v1-frame.json','ARIADNE_LEGACY_LOOP_MINIDUMP':'/caller-work/legacy/v2-minidump.json','ARIADNE_LEGACY_LOOP_FRAME':'/caller-work/legacy/v2-frame.json','ARIADNE_LEGACY_GUARD_REPORT':'/caller-work/legacy/guard-v1.json','TMPDIR':'/caller-work/tmp'}
env.update({'ARIADNE_CALLER_RECEIPT_DIR':str(out/'caller-receipts'),'ARIADNE_CALLER_WIRE_DIR':str(out/'caller-wires'),'ARIADNE_LEGACY_V2_COMPOSED_MINIDUMP':'/caller-work/legacy/v2-minidump.json','ARIADNE_LEGACY_V2_COMPOSED_FRAME':'/caller-work/legacy/v2-frame.json'})
manifest=json.loads(Path('/caller-work/source-manifest.json').read_text());(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for n,h in manifest['files'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h,n
results=[]
prior=Path('/caller-work/evidence/early-20261015T070419')
prior_manifest=json.loads((prior/'source-manifest.json').read_text())
model_files=[n for n in manifest['files'] if n.startswith(('Specs/PredicateAdmission','tests/bap/fixtures/caller-coverage/')) or n in ('Specs/AriadnePredicateAdmission.tla','Specs/check-predicate-admission.sh')]
for n in model_files:assert prior_manifest['files'][n]==manifest['files'][n],n
assert json.loads((prior/'predicate-model.json').read_text())['exit_code']==0
(out/'retained-model-evidence.json').write_text(json.dumps({'source':str(prior),'files':{n:manifest['files'][n] for n in model_files},'status':'retained-source-bound-pass'},indent=2)+'\n')
def run(name,command):
 start=time.monotonic();print('Gate:',name,flush=True)
 with(out/(name+'.log')).open('w')as f:p=subprocess.run(command,env=env,stdout=f,stderr=subprocess.STDOUT)
 r={'name':name,'command':command,'exit_code':p.returncode,'seconds':time.monotonic()-start};(out/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n');print(name,'PASS'if p.returncode==0 else'FAIL',flush=True)
 if p.returncode:print((out/(name+'.log')).read_text(errors='replace')[-7000:],flush=True)
 return r
import shutil
previous=Path('/caller-work/evidence/native-feedback-20261015T072430')
for name in ('caller-receipts','caller-wires'):shutil.copytree(previous/name,out/name)
buildout=root/'target'/out.name
results.append(run('native-controls',['python3','tests/bap/caller_coverage_native_controls.py','--native-dir','target/caller-native','--output',str(buildout),'--receipt-dir',str(out/'caller-receipts'),'--wire-dir',str(out/'caller-wires'),'--mutations']))
if buildout.exists():shutil.copytree(buildout,out/'native-controls')
(out/'gates.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results),flush=True)
raise SystemExit(0 if all(r['exit_code']==0 for r in results)else 1)
