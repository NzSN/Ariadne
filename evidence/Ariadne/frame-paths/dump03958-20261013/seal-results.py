from pathlib import Path
import hashlib,json,gzip,tarfile
base=Path('/home/jlc/ariadne-p4-20261010/work/frame-paths-dump03958-20261013')
repo=Path('/home/jlc/ariadne-p4-20261010/work/Repos/Ariadne-dump-retry-b5d56b7')
files=[]
for p in base.rglob('*'):
 if not p.is_file() or p.name=='original.dmp' or p.name.endswith('.long-type.txt') or p.name in ['frame_probe','blocker_probe','results.tar.gz']:continue
 if p.suffix in ['.json','.txt','.log','.rs','.sh'] or p.name.endswith('.long-type-9512912044080105251.txt'):files.append(p)
for p in files:
 if p.stat().st_size>1024*1024:
  target=p.with_name(p.name+'.gz');target.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
 selected=[p if p.stat().st_size<=1024*1024 else p.with_name(p.name+'.gz') for p in files]
manifest={'schema':'ariadne.frame-path-attempt-artifacts/v1','sources':{str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['src','native/bap-core'] for p in (repo/folder).rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts},'executables':{name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in {'cli':repo/'target/retry-build/release/ariadne-minidump','native_helper':repo/'target/retry-native/ariadne-bap-core','api_probe':base/'frame_probe','blocker_probe':base/'blocker_probe'}.items()},'artifacts':{str(p.relative_to(base)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in selected}}
(base/'artifact-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');selected.append(base/'artifact-manifest.json')
with tarfile.open(base/'results.tar.gz','w:gz') as archive:
 for p in selected:archive.add(p,arcname=str(p.relative_to(base)),recursive=False)
print(json.dumps({'bytes':(base/'results.tar.gz').stat().st_size,'sha256':hashlib.sha256((base/'results.tar.gz').read_bytes()).hexdigest(),'files':len(selected)}))
