from pathlib import Path
import hashlib,json,os,subprocess,time
root=Path('/home/nzsn/Repos/Ariadne-caller-coverage-20261015');os.chdir(root)
out=Path('/caller-work/evidence')/('models-'+time.strftime('%Y%m%dT%H%M%S'));out.mkdir();print('Model artifacts:',out,flush=True)
manifest=json.loads(Path('/caller-work/source-manifest.json').read_text());(out/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for n,h in manifest['files'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h,n
with(out/'predicate-model.log').open('w')as f:
 p=subprocess.run(['bash','Specs/check-predicate-admission.sh'],stdout=f,stderr=subprocess.STDOUT)
r={'exit_code':p.returncode,'passed':p.returncode==0,'command':['bash','Specs/check-predicate-admission.sh']}
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
print((out/'predicate-model.log').read_text(errors='replace')[-6000:],flush=True)
raise SystemExit(p.returncode)
