from pathlib import Path
import os,json,hashlib,subprocess,time
root=Path('/home/nzsn/Repos/Ariadne-vector-registers-20261013');os.chdir(root)
out=Path('/work/vector-registers-20261013');out.mkdir(exist_ok=True)
env={**os.environ,'CARGO_TARGET_DIR':str(root/'target/vector-build'),'ARIADNE_BAP_CORE_DIR':str(root/'target/vector-native'),
     'ARIADNE_LLVM_MC':str(root/'target/ariadne-llvm-mc'),'ARIADNE_BAP_HELPER':str(root/'target/ariadne-bap-lift'),
     'BAP_RUNTIME_ROOT':str(root/'tmp/bap-setup/stable')}
gates=[]
def run(name,command):
 print('Gate:',name,flush=True);start=time.monotonic()
 with (out/(name+'.log')).open('w') as log:
  p=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
 gates.append({'name':name,'command':command,'exit_code':p.returncode,'seconds':time.monotonic()-start})
 (out/'gates.json').write_text(json.dumps(gates,indent=2)+'\n')
 print(name, 'PASS' if p.returncode==0 else 'FAIL',flush=True)
 if p.returncode:print((out/(name+'.log')).read_text()[-5000:],flush=True)
 return p.returncode==0
commands=[
 ('format',['cargo','fmt','--all','--','--check']),
 ('vector-fixtures',['python3','tests/input/fixtures/make_vector.py','--check']),
 ('profile-tests',['python3','-m','unittest','discover','-s','tools','-p','test_bap_profile_migration.py','-v']),
 ('native-contract-tests',['python3','-m','unittest','discover','-s','tools','-p','test_i5a_native_contract.py','-v']),
 ('default-tests',['cargo','test','--offline','--locked']),
 ('core-only-tests',['cargo','test','--offline','--locked','--no-default-features']),
 ('clippy',['cargo','clippy','--offline','--locked','--all-features','--all-targets','--','-D','warnings']),
 ('layout',['python3','tools/check_rust_layout.py']),
 ('native-producer',['cargo','test','--offline','--locked','--test','bap_native','--','--ignored']),
 ('producer-disagreements',['cargo','test','--offline','--locked','--test','bap_disagreement','--','--ignored']),
 ('capture-parity',['cargo','test','--offline','--locked','--test','input_bap_core','--','--ignored']),
 ('frame-path-native',['cargo','test','--offline','--locked','--test','input_frame_paths','--','--ignored']),
 ('release-build',['cargo','build','--offline','--locked','--release','--lib','--bin','ariadne-minidump','--bin','bap-admission-validate']),
]
for name,cmd in commands:run(name,cmd)
print('VALIDATION RUN COMPLETE',flush=True)
