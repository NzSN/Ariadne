from pathlib import Path
import os,json,subprocess,hashlib,time
root=Path('/home/nzsn/Repos/Ariadne-composed-20261014');os.chdir(root)
base=Path('/work/guarded-target-resolution-20261014');out=base/('generated-replay-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir();print('Generated replay artifacts:',out,flush=True)
env={**os.environ,'CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0','CARGO_BUILD_JOBS':'4','ARIADNE_BAP_CORE_DIR':str(root/'target/composed-native')}
original=Path('/home/nzsn/Repos/Ariadne/target/mbt-work/toolchain.json')
if original.exists():
 record=json.loads(original.read_text());framework=Path(record['root'])
 for name,digest in record['binaries'].items():assert hashlib.sha256((framework/'.lake/build/bin'/name).read_bytes()).hexdigest()==digest
 env['MIRRORS_ROOT']=str(framework)
with(out/'replay.log').open('w') as log:p=subprocess.run(['python3','tools/check_bap_core_replay.py','--helper-dir','target/composed-native','--output',str(out/'campaign')],env=env,stdout=log,stderr=subprocess.STDOUT)
print((out/'replay.log').read_text()[-6000:],flush=True)
(out/'exit-code.txt').write_text(str(p.returncode)+'\n')
raise SystemExit(p.returncode)
