from pathlib import Path
import gzip,hashlib,json,os,shutil,subprocess,tarfile
base=Path('/home/jlc/ariadne-p4-20261010');external=Path('/mnt/d/ariadne-caller-coverage-20261015');external.mkdir(exist_ok=True)
dest=external/'repo-final';dest.mkdir(exist_ok=True)
archive=Path('/mnt/d/ariadne-caller-coverage-source-20261015.tar.gz')
manifest=json.loads(Path('/mnt/d/ariadne-caller-coverage-source-manifest-20261015.json').read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['archive_sha256']
with tarfile.open(archive)as t:t.extractall(dest,filter='data')
for n,h in manifest['files'].items():assert hashlib.sha256((dest/n).read_bytes()).hexdigest()==h,n
for n in ['cargo-build','replay-build','mutations-build','tmp','evidence','legacy']:(external/n).mkdir(exist_ok=True)
target=dest/'target';target.mkdir(exist_ok=True)
links={'ariadne-bap-lift':'/home/nzsn/Repos/Ariadne/target/ariadne-bap-lift','bap-core-sdk':'/home/nzsn/Repos/Ariadne/target/bap-core-sdk','caller-build':'/caller-work/cargo-build','caller-replay-build':'/caller-work/replay-build','caller-mutations-build':'/caller-work/mutations-build'}
for n,v in links.items():
 p=target/n
 if not p.exists()and not p.is_symlink():p.symlink_to(v)
for n in ['caller-native','caller-llvm']:(target/n).mkdir(exist_ok=True)
p=dest/'tmp'
if not p.exists()and not p.is_symlink():p.symlink_to('/home/nzsn/Repos/Ariadne/tmp')
if not(dest/'.git').exists():subprocess.run(['git','init','-q',str(dest)],check=True)
subprocess.run(['git','-c','safe.directory='+str(dest),'-C',str(dest),'add','--all'],check=True)
for generation,stem in [('guarded-target-resolution/20261014/artifacts/dump-20261014T121127','v1'),('loop-aware-target-resolution/20261015/artifacts/dump-20261015T051409','v2')]:
 for name,source in [('minidump','frame-1/minidump-rust.json.gz'),('frame','frame-paths.json.gz')]:
  p=dest/'evidence/Ariadne'/generation/source;o=external/'legacy'/(stem+'-'+name+'.json')
  expected=int.from_bytes(p.read_bytes()[-4:],'little')
  if not o.exists()or o.stat().st_size!=expected:
   with gzip.open(p,'rb')as a,o.open('wb')as b:shutil.copyfileobj(a,b)
shutil.copy2(dest/'evidence/Ariadne/native-request-budget/20261014/artifacts/probe-expanded/guard-report.json',external/'legacy/guard-v1.json')
runner=(base/'run.sh').read_text()
old='--chdir /home/nzsn/Repos/Ariadne '
new='--bind /mnt/d/ariadne-caller-coverage-20261015 /caller-work --bind /mnt/d/ariadne-caller-coverage-20261015/repo-final /home/nzsn/Repos/Ariadne-caller-coverage-20261015 --ro-bind /mnt/d/ariadne-loop-aware-20261015 /loop-baseline --chdir /home/nzsn/Repos/Ariadne-caller-coverage-20261015 --setenv TMPDIR /caller-work/tmp '
assert old in runner;runner=runner.replace(old,new)
(external/'run.sh').write_text(runner)
shutil.copy2('/mnt/d/ariadne-caller-coverage-source-manifest-20261015.json',external/'source-manifest.json')
subprocess.run(['chown','-hR','jlc:jlc',str(external)],check=True)
print(json.dumps({'repo':str(dest),'files_verified':len(manifest['files']),'archive_sha256':manifest['archive_sha256'],'linux_free':shutil.disk_usage(base).free,'external_free':shutil.disk_usage(external).free}),flush=True)
