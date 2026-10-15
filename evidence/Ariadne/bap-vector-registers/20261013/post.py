from pathlib import Path
import os,json,subprocess,time
root=Path('/home/nzsn/Repos/Ariadne-vector-registers-20261013');os.chdir(root)
out=Path('/work/vector-registers-20261013');gates=[]
env={**os.environ,'CARGO_TARGET_DIR':str(root/'target/vector-build'),'ARIADNE_BAP_CORE_DIR':str(root/'target/vector-native'),
 'ARIADNE_LLVM_MC':str(root/'target/ariadne-llvm-mc'),'ARIADNE_BAP_HELPER':str(root/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(root/'tmp/bap-setup/stable')}
def run(name,cmd,environment=None):
 print('Gate:',name,flush=True);start=time.monotonic()
 with (out/(name+'.log')).open('w') as log:p=subprocess.run(cmd,env=environment or env,stdout=log,stderr=subprocess.STDOUT)
 gates.append({'name':name,'command':cmd,'exit_code':p.returncode,'seconds':time.monotonic()-start});(out/'post-gates.json').write_text(json.dumps(gates,indent=2)+'\n')
 print(name,'PASS' if p.returncode==0 else 'FAIL',flush=True)
 if p.returncode:print((out/(name+'.log')).read_text()[-4500:],flush=True)
 return p.returncode==0
layout_env=env.copy();layout_env.pop('CARGO_TARGET_DIR',None)
run('layout-root-target',['python3','tools/check_rust_layout.py'],layout_env)
if not run('release-validation-build',['cargo','build','--offline','--locked','--release','--features','validation','--lib','--bin','ariadne-minidump','--bin','bap-admission-validate']):raise SystemExit(1)
build=root/'target/vector-build/release'
driver=Path('/work/frame-paths-dump03958-20261013/frame_probe.rs')
blocker=Path('/work/frame-paths-dump03958-20261013/blocker_probe.rs')
libs=list((build/'deps').glob('libserde_json-*.rlib'));assert len(libs)==1
compile_env=dict(env,CARGO_MANIFEST_DIR=str(root))
for name,p in [('frame-probe',driver),('blocker-probe',blocker)]:
 cmd=['rustc','--edition=2024',str(p),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libs[0]),'-o',str(out/name)]
 if not run(name+'-build',cmd,compile_env):raise SystemExit(1)
dump='/work/frame-paths-dump03958-20261013/original.dmp'
run('frame-probe',[str(out/'frame-probe'),dump,str(out/'api-probe')])
run('blocker-probe',[str(out/'blocker-probe'),dump,str(out/'blocker-instruction.json')])
print('POST VALIDATION COMPLETE',flush=True)
