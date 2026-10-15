from pathlib import Path
import os,json,subprocess,time,shutil
root=Path('/home/nzsn/Repos/Ariadne-guard-admission-20261014');os.chdir(root)
base=Path('/work/guard-admission-20261014')
out=base/('validation-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir()
print('Validation artifacts:',out,flush=True)
env={**os.environ,'CARGO_TARGET_DIR':str(root/'target/guard-build'),'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0',
 'ARIADNE_TARGET_DIAGNOSTICS':'1','ARIADNE_BAP_CORE_DIR':str(root/'target/guard-native'),'ARIADNE_LLVM_MC':str(root/'target/ariadne-llvm-mc'),
 'ARIADNE_BAP_HELPER':str(root/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(root/'tmp/bap-setup/stable')}
gates=[]
def run(name,cmd,environment=None):
 print('Gate',name,flush=True);start=time.monotonic()
 with (out/(name+'.log')).open('w') as f:p=subprocess.run(cmd,env=environment or env,stdout=f,stderr=subprocess.STDOUT)
 gates.append({'name':name,'command':cmd,'exit_code':p.returncode,'seconds':time.monotonic()-start})
 (out/'gates.json').write_text(json.dumps(gates,indent=2)+'\n')
 print(name,'PASS' if p.returncode==0 else 'FAIL',flush=True)
 if p.returncode:print((out/(name+'.log')).read_text()[-6000:],flush=True)
 return p.returncode==0
run('native-build',['python3','native/bap-core/build.py','--output','target/guard-native'])
run('guard-native-parity',['cargo','test','--offline','--locked','--test','input_bap_core','guarded_frame_capture_has_native_parity_and_rejects_direct_proof_tampering','--','--ignored','--nocapture'])
run('format',['cargo','fmt','--all','--','--check'])
run('oracle',['python3','tests/bap/fixtures/guards/oracle.py','--check'])
run('guard-fixture',['python3','tests/input/fixtures/make_guard_frame.py','--check'])
run('default-tests',['cargo','test','--offline','--locked'])
run('core-only-tests',['cargo','test','--offline','--locked','--no-default-features'])
run('clippy',['cargo','clippy','--offline','--locked','--all-features','--all-targets','--','-D','warnings'])
layout_env=env.copy();layout_env.pop('CARGO_TARGET_DIR',None)
run('layout',['python3','tools/check_rust_layout.py'],layout_env)
run('native-kernels',['cargo','test','--offline','--locked','--test','bap_core_bootstrap','--test','bap_core_analysis','--test','bap_core_stateflow','--','--ignored'])
run('native-producer',['cargo','test','--offline','--locked','--test','bap_native','--','--ignored'])
run('capture-parity',['cargo','test','--offline','--locked','--test','input_bap_core','--','--ignored'])
run('frame-path-native',['cargo','test','--offline','--locked','--test','input_frame_paths','--','--ignored'])
run('release-build',['cargo','build','--offline','--locked','--release','--features','validation','--lib','--bin','ariadne-minidump'])
