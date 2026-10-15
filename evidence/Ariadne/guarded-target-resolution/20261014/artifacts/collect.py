from pathlib import Path
import os,json,hashlib,gzip,tarfile,subprocess,shutil
root=Path('/home/nzsn/Repos/Ariadne-composed-20261014');base=Path('/work/guarded-target-resolution-20261014');dest=base/'delivery';dest.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source={}
for prefix in ['src','tests','native','Specs','tools','mbt']:
 for p in (root/prefix).rglob('*'):
  if not p.is_file() or p.is_symlink() or '__pycache__' in p.parts or '_TTrace_' in p.name or p.suffix=='.md':continue
  if p.stat().st_size<16*1024*1024:source[str(p.relative_to(root))]=sha(p)
for name in ['Cargo.toml','Cargo.lock'] :source[name]=sha(root/name)
(dest/'source-files.json').write_text(json.dumps(source,indent=2,sort_keys=True)+'\n')
tools={}
for name in ['target/composed-native/ariadne-bap-core','target/composed-native/manifest.json','target/composed-build/release/libariadne.rlib','target/composed-build/release/ariadne-minidump','target/ariadne-bap-lift','target/ariadne-llvm-mc','native/bap-core/sdk.lock.json','native/bap/toolchain.lock.json']:
 p=root/name
 if p.is_file():tools[name]={'sha256':sha(p),'bytes':p.stat().st_size}
(dest/'tools.json').write_text(json.dumps(tools,indent=2,sort_keys=True)+'\n')
(dest/'rustc-version.txt').write_text(subprocess.check_output(['rustc','--version','--verbose'],text=True))
(dest/'cargo-version.txt').write_text(subprocess.check_output(['cargo','--version'],text=True))
# Collect every run, including failed controls, without overwriting their identities.
with tarfile.open(str(base/'evidence-export.tar.gz'),'w:gz') as tar:
 for p in base.iterdir():
  if p.name=='delivery' or p.is_dir() or p.suffix in ['.py','.rs','.sh','.log']:tar.add(p,arcname='artifacts/'+p.name)
 for name in ['composed-native','composition-frontier-controls','conditional-write-native-controls','infeasible-loop-native-controls','native-composition-mutants','actual-infeasible-replay-1','actual-infeasible-replay-0','native-order-red-controls']:
  p=root/'target'/name
  if p.exists():tar.add(p,arcname='artifacts/'+name)
 for p in Path('/tmp').glob('ariadne-guarded-target-resolution.*'):
  if p.is_dir():tar.add(p,arcname='artifacts/models/'+p.name)
 for name in ['dump-probe.rs','run-dump-probe.sh','qualify.py','run-native-frontier.py','run-native-mutations.py']:
  p=root/'target/guarded-target-resolution-20261014'/name
  if p.exists():tar.add(p,arcname='reproduce/'+name)
archive=Path(str(base/'evidence-export.tar.gz'))
print(json.dumps({'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'source_files':len(source),'tool_files':len(tools)}))
