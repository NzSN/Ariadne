from pathlib import Path
import hashlib,json,os,subprocess,time,concurrent.futures
root=Path('/home/nzsn/Repos/Ariadne-loop-aware-20261015');os.chdir(root)
out=Path('/loop-work/evidence')/('early-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir();print('Artifacts:',out,flush=True)
env={**os.environ,'CARGO_TARGET_DIR':str(root/'target/loop-aware-build'),'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_PROFILE_TEST_DEBUG':'0','CARGO_BUILD_JOBS':'4','ARIADNE_BAP_CORE_DIR':str(root/'target/loop-aware-native'),'ARIADNE_BAP_HELPER':str(root/'target/ariadne-bap-lift'),'ARIADNE_LLVM_MC':str(root/'target/ariadne-llvm-mc'),'BAP_RUNTIME_ROOT':str(root/'tmp/bap-setup/stable'),'ARIADNE_LEGACY_COMPOSED_MINIDUMP':'/loop-work/legacy/minidump.json','ARIADNE_LEGACY_COMPOSED_FRAME':'/loop-work/legacy/frame-paths.json','TMPDIR':'/loop-work/tmp'}
env['ARIADNE_LOOP_RECEIPT_DIR']=str(out/'loop-receipts')
def run(name,command):
    start=time.monotonic();print('Gate:',name,flush=True)
    with (out/(name+'.log')).open('w') as log:p=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
    result={'name':name,'command':command,'exit_code':p.returncode,'seconds':time.monotonic()-start}
    (out/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(name,'PASS' if p.returncode==0 else 'FAIL',flush=True)
    if p.returncode:print((out/(name+'.log')).read_text()[-7000:],flush=True)
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures=[pool.submit(run,'loop-model',['bash','Specs/check-loop-target-closure.sh']),pool.submit(run,'rust-loop-tests',['cargo','test','--offline','--locked','--lib','bap::target_resolution::loop_tests']),pool.submit(run,'native-build',['python3','native/bap-core/build.py','--output','target/loop-aware-native'])]
    results=[f.result() for f in futures]
(out/'gates.json').write_text(json.dumps(results,indent=2)+'\n')
print('Summary:',json.dumps(results),flush=True)
