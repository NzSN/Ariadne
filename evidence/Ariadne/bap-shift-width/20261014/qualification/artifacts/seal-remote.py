from pathlib import Path
import hashlib,json,tarfile,shutil,subprocess,os
root=Path('/home/nzsn/Repos/Ariadne-bap-shift-count-20261014');out=Path('/work/bap-shift-width-20261014')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Keep all distinct failed and passing model attempts.
models=out/'models';models.mkdir(exist_ok=True)
for model in Path('/tmp').glob('ariadne-predicate-admission.*'):
 if not model.is_dir():continue
 dest=models/model.name;dest.mkdir(exist_ok=True)
 for p in model.glob('*'):
  if p.is_file() and p.suffix in ['.log','.txt','.sha256']:shutil.copy2(p,dest/p.name)
 if (model/'typecheck').exists():
  for p in (model/'typecheck').rglob('*'):
   if p.is_file() and p.suffix in ['.log','.json','.tla']:
    rel=p.relative_to(model);q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
for name in ['bap-shift-probe','bap-shift-probe-v2']:
 probe=root/'target'/name
 if probe.exists():
  dest=out/'asset-probes'/name;dest.mkdir(parents=True,exist_ok=True)
  for p in probe.iterdir():
   if p.is_file() and p.suffix in ['.log','.txt','.jsonl'] :shutil.copy2(p,dest/p.name)
mutations=root/'target/shift-mutations-v2-20261014'
if mutations.exists():
 (out/'mutations').mkdir(exist_ok=True)
 for p in mutations.rglob('*'):
  if p.is_file() and p.suffix in ['.json','.log'] and 'sut' not in p.relative_to(mutations).parts:
   q=out/'mutations'/p.relative_to(mutations);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
paths=[]
for folder in ['src','tests','native','Specs','tools','mbt']:
 for p in (root/folder).rglob('*'):
  if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix!='.md':paths.append(p)
paths.extend(root/p for p in ['Cargo.toml','Cargo.lock'])
sources={str(p.relative_to(root)):sha(p) for p in sorted(set(paths))}
manifest=json.loads((root/'target/shift-native/manifest.json').read_text())
(out/'source-and-tools.json').write_text(json.dumps({'schema':'ariadne.bap-shift-source-tools/v1','sourceHashes':sources,
 'nativeManifest':manifest,'executables':{str(p.relative_to(root)):sha(p) for p in [root/'target/shift-build/release/ariadne-minidump',root/'target/ariadne-bap-lift',root/'target/ariadne-llvm-mc']},
 'remote':'windows-dev WSL isolated namespace','rustc':subprocess.check_output(['rustc','--version']).decode().strip(),
 'cargo':subprocess.check_output(['cargo','--version']).decode().strip()},indent=2)+'\n')
shutil.copy2(root/'target/shift-native/manifest.json',out/'native-manifest.json')
archive=Path('/work/bap-shift-evidence-20261014.tar.gz');entries={}
with tarfile.open(archive,'w:gz') as tar:
 for p in sorted(out.rglob('*')):
  if not p.is_file() or p.name in ['frame_probe','expanded_probe','repro','original.dmp']:continue
  if p.suffix not in ['.json','.jsonl','.log','.txt','.sha256','.rs','.sh','.py','.tla']:continue
  if p.stat().st_size>16*1024*1024:raise RuntimeError('unexpected large artifact '+str(p))
  rel=str(p.relative_to(out));entries[rel]={'sha256':sha(p),'bytes':p.stat().st_size};tar.add(p,arcname=rel,recursive=False)
with tarfile.open(archive,'r:gz') as tar:
 actual={m.name:hashlib.sha256(tar.extractfile(m).read()).hexdigest() for m in tar.getmembers() if m.isfile()}
assert actual=={k:v['sha256'] for k,v in entries.items()}
record={'schema':'ariadne.guard-artifacts/v1','archiveSha256':sha(archive),'entries':entries,'verified':True}
Path('/work/bap-shift-artifact-manifest-20261014.json').write_text(json.dumps(record,indent=2)+'\n')
print('sealed',len(entries),'artifacts;',archive.stat().st_size,'archivebytes;',record['archiveSha256'])
