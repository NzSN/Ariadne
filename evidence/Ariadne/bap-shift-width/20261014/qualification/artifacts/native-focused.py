from pathlib import Path
import os,json,subprocess,time
root=Path('/home/nzsn/Repos/Ariadne-bap-shift-count-20261014');os.chdir(root);out=Path('/work/bap-shift-width-20261014')
env={**os.environ,'CARGO_TARGET_DIR':str(root/'target/shift-build'),'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','CARGO_BUILD_JOBS':'4','ARIADNE_BAP_CORE_DIR':str(root/'target/shift-native'),'ARIADNE_BAP_HELPER':str(root/'target/ariadne-bap-lift'),'ARIADNE_LLVM_MC':str(root/'target/ariadne-llvm-mc'),'BAP_RUNTIME_ROOT':str(root/'tmp/bap-setup/stable'),'ARIADNE_TARGET_DIAGNOSTICS':'1'}
def run(name,cmd):
 print('Gate',name,flush=True);t=time.monotonic()
 with (out/(name+'.log')).open('w') as f:p=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
 print(name,'PASS' if p.returncode==0 else 'FAIL','seconds',round(time.monotonic()-t,3),flush=True)
 if p.returncode:print((out/(name+'.log')).read_text()[-8000:],flush=True)
 return p.returncode
run('shift-producer-exact',['cargo','test','--offline','--locked','--test','bap_native','vector_producer_tracks_coarse_state_and_retains_alignment_refusal','--','--ignored','--nocapture'])
run('shift-guarded-native-exact',['cargo','test','--offline','--locked','--test','input_bap_core','captured_xorps_shift_width_has_guarded_native_parity_and_rejects_rehashed_nonshift','--','--ignored','--nocapture'])
