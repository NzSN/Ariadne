from pathlib import Path
import gzip,hashlib,json,os,shutil,subprocess,tarfile
base=Path('/home/jlc/ariadne-p4-20261010')
external=Path('/mnt/d/ariadne-loop-aware-20261015');external.mkdir(exist_ok=True)
dest=external/'repo';dest.mkdir(exist_ok=True)
archive=Path('/mnt/d/ariadne-loop-aware-source-20261015.tar.gz')
manifest=json.loads(Path('/mnt/d/ariadne-loop-aware-source-manifest-20261015.json').read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==manifest['archive_sha256']
with tarfile.open(archive) as t:t.extractall(dest,filter='data')
for name,h in manifest['files'].items():assert hashlib.sha256((dest/name).read_bytes()).hexdigest()==h,name
for name in ('cargo-build','native-build','replay-build','mutations-build','tmp','evidence','legacy'):(external/name).mkdir(exist_ok=True)
target=dest/'target';target.mkdir(exist_ok=True)
for name,link in {'ariadne-bap-lift':'/home/nzsn/Repos/Ariadne/target/ariadne-bap-lift','ariadne-llvm-mc':'/home/nzsn/Repos/Ariadne/target/ariadne-llvm-mc','bap-core-sdk':'/home/nzsn/Repos/Ariadne/target/bap-core-sdk','loop-aware-build':'/loop-work/cargo-build','loop-aware-replay-build':'/loop-work/replay-build','loop-aware-mutations-build':'/loop-work/mutations-build'}.items():
    p=target/name
    if not p.exists() and not p.is_symlink():p.symlink_to(link)
p=target/'loop-aware-native'
if p.is_symlink() and os.readlink(p)=='/loop-work/native-build':p.unlink()
p.mkdir(exist_ok=True)
p=dest/'tmp'
if not p.exists() and not p.is_symlink():p.symlink_to('/home/nzsn/Repos/Ariadne/tmp')
if not (dest/'.git').exists():subprocess.run(['git','init','-q',str(dest)],check=True)
subprocess.run(['git','-c','safe.directory='+str(dest),'-C',str(dest),'add','--all'],check=True)
for source,name in [('frame-1/minidump-rust.json.gz','minidump.json'),('frame-paths.json.gz','frame-paths.json')]:
    p=dest/'evidence/Ariadne/guarded-target-resolution/20261014/artifacts/dump-20261014T121127'/source
    out=external/'legacy'/name
    expected_size=int.from_bytes(p.read_bytes()[-4:],'little')
    if not out.exists() or out.stat().st_size!=expected_size:
        with gzip.open(p,'rb') as a,out.open('wb') as b:shutil.copyfileobj(a,b)
runner=(base/'run.sh').read_text()
runner=runner.replace('--chdir /home/nzsn/Repos/Ariadne ', '--bind /mnt/d/ariadne-loop-aware-20261015 /loop-work --bind /mnt/d/ariadne-loop-aware-20261015/repo /home/nzsn/Repos/Ariadne-loop-aware-20261015 --chdir /home/nzsn/Repos/Ariadne-loop-aware-20261015 --setenv TMPDIR /loop-work/tmp ')
(external/'run.sh').write_text(runner)
shutil.copy2('/mnt/d/ariadne-loop-aware-early-20261015.py',external/'early.py')
shutil.copy2('/mnt/d/ariadne-loop-aware-source-manifest-20261015.json',external/'source-manifest.json')
subprocess.run(['chown','-hR','jlc:jlc',str(external)],check=True)
print(json.dumps({'repo':str(dest),'archive_sha256':manifest['archive_sha256'],'files_verified':len(manifest['files']),'linux_free':shutil.disk_usage(base).free,'external_free':shutil.disk_usage(external).free}))
