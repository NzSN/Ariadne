from pathlib import Path
import os,json,subprocess,time,re
root=Path('/home/nzsn/Repos/Ariadne-bap-shift-count-20261014');os.chdir(root)
base=Path('/work/bap-shift-width-20261014');out=base/('validation-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir();print('Validation artifacts:',out,flush=True)
env={**os.environ,'CARGO_TARGET_DIR':str(root/'target/shift-build'),'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','CARGO_BUILD_JOBS':'4','ARIADNE_BAP_CORE_DIR':str(root/'target/shift-native'),'ARIADNE_BAP_HELPER':str(root/'target/ariadne-bap-lift'),'ARIADNE_LLVM_MC':str(root/'target/ariadne-llvm-mc'),'BAP_RUNTIME_ROOT':str(root/'tmp/bap-setup/stable'),'ARIADNE_TARGET_DIAGNOSTICS':'1'}
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
run('shift-units',['cargo','test','--offline','--locked','--lib','bap::shift_projection_tests'],require_tests=True)
run('oracle',['python3','tests/bap/fixtures/shifts/oracle.py','--check'])
run('asset-probe',['python3','tools/check_bap_shift_probe.py','--runtime',str(root/'tmp/bap-setup/stable'),'--build-dir','target/bap-shift-probe-v2','--output',str(out/'asset-probe.json')])
run('profile-controls',['python3','-m','unittest','discover','-s','tools','-p','test_bap_profile_migration.py'])
run('fixture',['python3','tests/input/fixtures/make_shift_frame.py','--check'])
run('format',['cargo','fmt','--all','--','--check'])
run('default-tests',['cargo','test','--offline','--locked'],require_tests=True)
run('core-only',['cargo','test','--offline','--locked','--no-default-features'],require_tests=True)
run('clippy',['cargo','clippy','--offline','--locked','--all-features','--all-targets','--','-D','warnings'])
layoutenv=env.copy();layoutenv.pop('CARGO_TARGET_DIR',None);run('layout',['python3','tools/check_rust_layout.py'],layoutenv)
run('native-build',['python3','native/bap-core/build.py','--output','target/shift-native'])
run('producer',['cargo','test','--offline','--locked','--test','bap_native','--','--ignored'],require_tests=True)
run('native-kernels',['cargo','test','--offline','--locked','--test','bap_core_bootstrap','--test','bap_core_analysis','--test','bap_core_stateflow','--','--ignored'],require_tests=True)
run('native-capture',['cargo','test','--offline','--locked','--test','input_bap_core','--','--ignored'],require_tests=True)
run('native-frame-path',['cargo','test','--offline','--locked','--test','input_frame_paths','--','--ignored'],require_tests=True)
run('release-build',['cargo','build','--offline','--locked','--release','--features','validation','--lib','--bin','ariadne-minidump'])
