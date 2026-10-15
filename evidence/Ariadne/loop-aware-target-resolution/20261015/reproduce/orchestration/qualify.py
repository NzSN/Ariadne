from pathlib import Path
import hashlib,json,os,re,subprocess,time
root=Path('/home/nzsn/Repos/Ariadne-loop-aware-20261015');os.chdir(root)
base=Path('/loop-work/evidence');out=base/('validation-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir();print('Validation artifacts:',out,flush=True)
env={**os.environ,'CARGO_TARGET_DIR':str(root/'target/loop-aware-build'),'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','CARGO_BUILD_JOBS':'4','ARIADNE_BAP_CORE_DIR':str(root/'target/loop-aware-native'),'ARIADNE_BAP_HELPER':str(root/'target/ariadne-bap-lift'),'ARIADNE_LLVM_MC':str(root/'target/ariadne-llvm-mc'),'BAP_RUNTIME_ROOT':str(root/'tmp/bap-setup/stable'),'ARIADNE_LEGACY_COMPOSED_MINIDUMP':'/loop-work/legacy/minidump.json','ARIADNE_LEGACY_COMPOSED_FRAME':'/loop-work/legacy/frame-paths.json','ARIADNE_LOOP_RECEIPT_DIR':str(out/'loop-receipts'),'ARIADNE_COMPOSITION_WIRE':str(out/'passing-combined-wire.json'),'TMPDIR':'/loop-work/tmp'}
gates=[]
def run(name,cmd,require_tests=False,extra=None):
    start=time.monotonic();print('Gate:',name,flush=True)
    selected_env={**env,**(extra or {})}
    if name=='layout':selected_env.pop('CARGO_TARGET_DIR',None)
    with (out/(name+'.log')).open('w') as f:
        p=subprocess.run(cmd,env=selected_env,stdout=f,stderr=subprocess.STDOUT)
    text=(out/(name+'.log')).read_text(errors='replace');passed=p.returncode==0
    if require_tests:passed=passed and bool(re.search(r'test result: ok\. [1-9][0-9]* passed',text))
    record={'name':name,'command':cmd,'exit_code':p.returncode,'passed':passed,'seconds':time.monotonic()-start};gates.append(record)
    (out/'gates.json').write_text(json.dumps(gates,indent=2)+'\n')
    print(name,'PASS' if passed else 'FAIL',flush=True)
    if not passed:print(text[-9500:],flush=True);raise SystemExit(1)
manifest=json.loads(Path('/loop-work/source-manifest.json').read_text())
def verify_sources():
    for n,h in manifest['files'].items():
        if hashlib.sha256((root/n).read_bytes()).hexdigest()!=h:raise RuntimeError('source changed: '+n)
verify_sources();(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
run('format',['cargo','fmt','--all','--','--check'])
run('loop-fixtures',['python3','tests/bap/fixtures/loop-closure/extract.py','--check'])
run('loop-oracle',['python3','tests/bap/fixtures/loop-closure/oracle.py','--check','--output',str(out/'oracle.json')])
run('loop-tests',['cargo','test','--offline','--locked','--lib','bap::target_resolution::loop_tests'],True)
run('loop-publication-regression',['cargo','test','--offline','--locked','--lib','loop_publication_binds_unattempted_seed_and_nonlocal_call_endpoints'],True)
run('default-tests',['cargo','test','--offline','--locked'],True)
run('core-only',['cargo','test','--offline','--locked','--no-default-features'],True)
run('clippy',['cargo','clippy','--offline','--locked','--all-features','--all-targets','--','-D','warnings'])
run('layout',['python3','tools/check_rust_layout.py'])
local_docs=json.loads(Path('/loop-work/local-documentation.json').read_text())
assert local_docs['exit_code']==0
for n,h in local_docs['files'].items():assert manifest['files'][n]==h,n
(out/'local-documentation.json').write_text(json.dumps(local_docs,indent=2)+'\n')
print('Documentation: source-bound local complete-checkout PASS',flush=True)
run('native-build',['python3','native/bap-core/build.py','--output','target/loop-aware-native'])
run('native-loop-controls',['python3','tests/bap/newloop_native_controls.py','--native-dir','target/loop-aware-native','--receipt-dir',str(out/'loop-receipts'),'--output','target/loop-aware-native-controls-'+out.name,'--mutations'])
run('legacy-combined-replay',['cargo','test','--offline','--locked','--test','input_frame_paths','retained_combined_v1_minidump_and_frame_reports_replay_after_upgrade','--','--ignored'],True)
run('native-targets',['cargo','test','--offline','--locked','--lib','input::materialize::target_resolution_tests','--','--ignored'],True)
run('native-kernels',['cargo','test','--offline','--locked','--test','bap_core_bootstrap','--test','bap_core_analysis','--test','bap_core_stateflow','--','--ignored'],True)
run('native-capture',['cargo','test','--offline','--locked','--test','input_bap_core','--','--ignored'],True)
run('native-composition',['cargo','test','--offline','--locked','--lib','actual_bap_pending_store_targets_and_native_rust_results_agree','--','--ignored'],True)
run('native-composition-controls',['python3','tests/bap/composition_native_controls.py','--helper','target/loop-aware-native/ariadne-bap-core','--input',str(out/'passing-combined-wire.json'),'--output',str(out/'native-composition-controls.json')])
run('native-frame-reports',['cargo','test','--offline','--locked','--test','input_frame_paths','--','--ignored'],True)
run('target-model',['bash','Specs/check-target-resolution.sh'])
run('composition-model',['bash','Specs/check-guarded-target-resolution.sh'])
run('loop-model',['bash','Specs/check-loop-target-closure.sh'])
run('contract-tools',['python3','-m','unittest','discover','-s','tools','-p','test_bap_core_contract.py'])
run('release-build',['cargo','build','--offline','--locked','--release','--features','validation','--lib','--bin','ariadne-minidump'])
verify_sources();(out/'complete.json').write_text(json.dumps({'all_gates_pass':True,'gates':gates,'source_files':len(manifest['files'])},indent=2)+'\n')
print('ALL QUALIFICATION GATES PASSED',flush=True)
