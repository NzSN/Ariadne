from pathlib import Path
import os,json,subprocess,time,re,hashlib
root=Path('/home/nzsn/Repos/Ariadne-request-budget-20261014');os.chdir(root)
base=Path('/work/native-request-budget-20261014');out=base/('validation-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir();print('Validation artifacts:',out,flush=True)
env={**os.environ,'CARGO_TARGET_DIR':str(root/'target/request-budget-build'),'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','CARGO_BUILD_JOBS':'4','ARIADNE_BAP_CORE_DIR':str(root/'target/request-budget-native'),'ARIADNE_BAP_HELPER':str(root/'target/ariadne-bap-lift'),'ARIADNE_LLVM_MC':str(root/'target/ariadne-llvm-mc'),'BAP_RUNTIME_ROOT':str(root/'tmp/bap-setup/stable'),'ARIADNE_TARGET_DIAGNOSTICS':'1'}
gates=[]
def run(name,cmd,custom_env=None,require_tests=False):
 print('Gate',name,flush=True);t=time.monotonic()
 with (out/(name+'.log')).open('w') as f:p=subprocess.run(cmd,env=custom_env or env,stdout=f,stderr=subprocess.STDOUT)
 log=(out/(name+'.log')).read_text();passed=p.returncode==0
 if require_tests and not re.search(r'test result: ok\. [1-9][0-9]* passed',log):passed=False
 gates.append({'name':name,'command':cmd,'exit_code':p.returncode,'passed':passed,'seconds':time.monotonic()-t});(out/'gates.json').write_text(json.dumps(gates,indent=2)+'\n')
 print(name,'PASS' if passed else 'FAIL',flush=True)
 if not passed:print(log[-6500:],flush=True)
 return passed
if not run('format-apply',['cargo','fmt','--all']):raise SystemExit(1)
if not run('guard-oracle',['python3','tests/bap/fixtures/guards/oracle.py','--check']):raise SystemExit(1)
if not run('format',['cargo','fmt','--all','--','--check']):raise SystemExit(1)
if not run('guard-units',['cargo','test','--offline','--locked','--lib','bap::guard_admission_tests'],require_tests=True):raise SystemExit(1)
if not run('default-tests',['cargo','test','--offline','--locked'],require_tests=True):raise SystemExit(1)
if not run('core-only',['cargo','test','--offline','--locked','--no-default-features'],require_tests=True):raise SystemExit(1)
if not run('clippy',['cargo','clippy','--offline','--locked','--all-features','--all-targets','--','-D','warnings']):raise SystemExit(1)
layoutenv=env.copy();layoutenv.pop('CARGO_TARGET_DIR',None)
if not run('layout',['python3','tools/check_rust_layout.py'],layoutenv):raise SystemExit(1)
if not run('native-build',['python3','native/bap-core/build.py','--output','target/request-budget-native']):raise SystemExit(1)
if not run('native-kernels',['cargo','test','--offline','--locked','--test','bap_core_bootstrap','--test','bap_core_analysis','--test','bap_core_stateflow','--','--ignored'],require_tests=True):raise SystemExit(1)
if not run('native-capture',['cargo','test','--offline','--locked','--test','input_bap_core','--','--ignored'],require_tests=True):raise SystemExit(1)
if not run('native-frame-path',['cargo','test','--offline','--locked','--test','input_frame_paths','--','--ignored'],require_tests=True):raise SystemExit(1)
if not run('contract-tools',['python3','-m','unittest','discover','-s','tools','-p','test_bap_core_contract.py']):raise SystemExit(1)
if not run('guard-mutation-seams',['python3','tools/check_guard_admission_mutations.py','--check-seams']):raise SystemExit(1)
if not run('release-build',['cargo','build','--offline','--locked','--release','--features','validation','--lib','--bin','ariadne-minidump']):raise SystemExit(1)
print('All gates passed',flush=True)
