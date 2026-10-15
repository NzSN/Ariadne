from pathlib import Path
import concurrent.futures,hashlib,json,os,subprocess,time
root=Path('/home/nzsn/Repos/Ariadne-caller-coverage-20261015');os.chdir(root)
out=Path('/caller-work/evidence')/('early-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir();print('Early artifacts:',out,flush=True)
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
with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:
 futures=[pool.submit(run,'rust-terminal',['cargo','test','--offline','--locked','--lib','bap::terminal_control::tests']),pool.submit(run,'native-build',['python3','native/bap-core/build.py','--output','target/caller-native']),pool.submit(run,'llvm-build',['bash','native/llvm_mc/build.sh','target/caller-llvm/ariadne-llvm-mc'])]
 results=[f.result()for f in futures]
if next(r for r in results if r['name']=='rust-terminal')['exit_code']==0:
 for name,pattern in [('rust-guard','bap::guard_admission_tests'),('rust-composition','input::materialize::composition_tests')]:results.append(run(name,['cargo','test','--offline','--locked','--lib',pattern]))
if all(r['exit_code']==0 for r in results):
 results.append(run('actual-load-export',['cargo','test','--offline','--locked','--lib','actual_movaps_load_guard_outcomes_export_checked_native_inputs','--','--ignored','--nocapture']))
if all(r['exit_code']==0 for r in results):
 results.append(run('native-controls',['python3','tests/bap/caller_coverage_native_controls.py','--native-dir','target/caller-native','--output',str(out/'native-controls'),'--receipt-dir',str(out/'caller-receipts'),'--wire-dir',str(out/'caller-wires'),'--mutations']))
(out/'gates.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results),flush=True)
raise SystemExit(0 if all(r['exit_code']==0 for r in results)else 1)
