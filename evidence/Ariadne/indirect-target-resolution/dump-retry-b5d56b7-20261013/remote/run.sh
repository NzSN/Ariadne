#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
  base=/home/jlc/ariadne-p4-20261010
  checkout="$base/work/Repos/Ariadne-dump-retry-b5d56b7"
  output="$base/work/dump048B/retry-b5d56b7"
  printf '%s\n' '7c46f05e60cf9f61d53dd5e4b898176ba5504760fafc60340ef0d75cf00c4ffb  /mnt/d/ariadne-dump-retry-b5d56b7.tar.gz' | sha256sum --check
  test ! -e "$checkout"
  test ! -e "$output"
  mkdir -p "$checkout" "$output"
  tar -xzf /mnt/d/ariadne-dump-retry-b5d56b7.tar.gz -C "$checkout"
  mkdir -p "$checkout/target" "$checkout/tmp/bap-setup"
  ln -s /home/nzsn/Repos/Ariadne/target/bap-core-sdk "$checkout/target/bap-core-sdk"
  ln -s /home/nzsn/Repos/Ariadne/target/ariadne-bap-lift "$checkout/target/ariadne-bap-lift"
  ln -s /home/nzsn/Repos/Ariadne/target/ariadne-llvm-mc "$checkout/target/ariadne-llvm-mc"
  ln -s /home/nzsn/Repos/Ariadne/tmp/bap-setup/stable "$checkout/tmp/bap-setup/stable"
  cp "$0" "$output/run.sh"
  exec "$base/run.sh" bash /work/dump048B/retry-b5d56b7/run.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-dump-retry-b5d56b7
output=/work/dump048B/retry-b5d56b7
exec > >(tee -a "$output/progress.log") 2>&1
printf '%s\n' 'Phase: verify original dump and capture environment'
printf '%s\n' '5fea4ca614706fe0040ed3231efee0edf9ce4004a51d902bb581025b48bade08  /work/dump048B/original.dmp' | sha256sum --check
uname -a > "$output/platform.log"
rustc --version >> "$output/platform.log"
cargo --version >> "$output/platform.log"
uptime >> "$output/platform.log"
free -m >> "$output/platform.log"
printf '%s\n' 'Phase: rebuild native helper from published sources'
python3 native/bap-core/build.py --output target/retry-native > "$output/native-build.log" 2>&1
export ARIADNE_BAP_CORE_DIR="$PWD/target/retry-native"
printf '%s\n' 'Phase: build current release library and CLI'
cargo build --offline --locked --release --features validation --target-dir target/retry-build --lib --bin ariadne-minidump --bin target-resolution-validate > "$output/rust-build.log" 2>&1
printf '%s\n' 'Phase: exercise all portable and pinned target-resolution tests'
cargo test --offline --locked --release --features validation --target-dir target/retry-build --lib target_resolution -- --include-ignored --test-threads=1 > "$output/native-fixtures.log" 2>&1
printf '%s\n' 'Phase: compile bounded diagnostic driver for complete native/Rust state comparison'
python3 - <<'DRIVER'
from pathlib import Path
import json,os,subprocess
root=Path.cwd(); build=root/'target/retry-build/release';out=Path('/work/dump048B/retry-b5d56b7')
source=(root/'src/bin/target_resolution_validate.rs').read_text()
assert source.count('let config = ariadne::bap::core_session::CoreConfig::from_directory(')==1
source=source.replace('let config = ariadne::bap::core_session::CoreConfig::from_directory(', 'let mut config = ariadne::bap::core_session::CoreConfig::from_directory(',1)
assert source.count('    let mut records = Vec::new();')==1
source=source.replace('    let mut records = Vec::new();','    config.timeout = std::time::Duration::from_secs(60);\n    let mut records = Vec::new();',1)
driver=root/'target/retry-diagnostic.rs';driver.write_text(source)
(out/'diagnostic-driver.rs.txt').write_text(source)
command=['rustc','--edition=2024','--crate-name','dump_retry_diagnostic',str(driver),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib')]
for crate in ['sha2','serde_json']:
 libs=list((build/'deps').glob('lib'+crate+'-*.rlib'));assert len(libs)==1,(crate,libs)
 command.extend(['--extern',crate+'='+str(libs[0])])
command.extend(['-o',str(root/'target/retry-diagnostic')])
subprocess.run(command,check=True,env=dict(os.environ,CARGO_MANIFEST_DIR=str(root)))
(out/'diagnostic-build.json').write_text(json.dumps({'command':command,'difference':'Only public CoreConfig response timeout is set to 60000 ms; analyzer and capture sources are unchanged.','cli_timing_credit':False},indent=2)+'\n')
DRIVER
export ARIADNE_TARGET_DIAGNOSTICS=1
printf '%s\n' 'Phase: compare complete native/Rust states on the original full dump'
/usr/bin/time -v target/retry-diagnostic /work/dump048B/original.dmp "$output/case" > "$output/state-parity.log" 2> "$output/state-parity-timing.log"
printf '%s\n' 'Phase: measure current native CLI explanation'
/usr/bin/time -v target/retry-build/release/ariadne-minidump /work/dump048B/original.dmp --decoder-reference target/ariadne-llvm-mc --entry 0x00007ff640079640 --seed 0x00007ff640079670 --resolve-indirect-targets --max-artifact-bytes 2147483648 --bap-core-response-timeout-ms 30000 --explain-fault-address 0x00007ff640079670 --memory-access 0 --explanation-only --format json > "$output/native-explanation.json" 2> "$output/native-cli-timing.log"
printf '%s\n' 'Phase: measure current Rust CLI explanation'
/usr/bin/time -v target/retry-build/release/ariadne-minidump /work/dump048B/original.dmp --decoder-reference target/ariadne-llvm-mc --entry 0x00007ff640079640 --seed 0x00007ff640079670 --resolve-indirect-targets --max-artifact-bytes 2147483648 --analysis-backend rust --explain-fault-address 0x00007ff640079670 --memory-access 0 --explanation-only --format json > "$output/rust-explanation.json" 2> "$output/rust-cli-timing.log"
printf '%s\n' 'Phase: validate oracle, state and CLI parity; seal artifacts'
python3 - <<'SEAL'
from pathlib import Path
import gzip,hashlib,json,platform,re,tarfile
root=Path.cwd();out=Path('/work/dump048B/retry-b5d56b7')
case=json.loads((out/'case/qualification.json').read_text())
receipt=json.loads((out/'case/target-resolution.json').read_text())
dispatch=next(r for r in receipt['resolutions'] if r['site']=='0x00007ff64007968b')
oracle=json.loads((root/'tests/bap/fixtures/target-resolution-table.json').read_text())
assert dispatch['targets']==oracle['unique_targets']
assert not dispatch['complete'] and case['native_rust_state_equal']
for backend in ['native','rust']:
 data=(out/f'{backend}-explanation.json').read_bytes();value=json.loads(data)
 assert value['status']=='partial'
 (out/f'{backend}-explanation.json.gz').write_bytes(gzip.compress(data,mtime=0))
assert (out/'native-explanation.json').read_bytes()==(out/'rust-explanation.json').read_bytes()
sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['src','tests','native/bap','native/bap-core'] for p in (root/folder).rglob('*') if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts}
for n in ['Cargo.toml','Cargo.lock']:sources[n]=hashlib.sha256((root/n).read_bytes()).hexdigest()
manifest=json.loads((root/'target/retry-native/manifest.json').read_text())
for n,h in manifest['handshake']['source_hashes'].items():assert sources['native/bap-core/'+n]==h
(out/'native-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
executables={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in {'cli':root/'target/retry-build/release/ariadne-minidump','diagnostic':root/'target/retry-diagnostic','native':root/'target/retry-native/ariadne-bap-core','lifter':root/'target/ariadne-bap-lift','decoder':root/'target/ariadne-llvm-mc'}.items()}
report={'schema':'ariadne.dump-retry/v1','source_commit':'b5d56b7256f62f4bafff4cac3e0500664f41fd39','dump_sha256':case['dump_sha256'],'dump_bytes':Path('/work/dump048B/original.dmp').stat().st_size,'platform':platform.platform(),'sources':sources,'executables':executables,'case':case,'targets':dispatch['targets'],'target_complete':dispatch['complete'],'native_rust_cli_equal':True,'explanation_sha256':hashlib.sha256((out/'native-explanation.json').read_bytes()).hexdigest(),'historical_state_sha256':'4b5c6d947ac8622932e63d8731733e4cf328b7d7401302fcc68ffa0d2ffcf30c','historical_state_equal':all(r['state_sha256']=='4b5c6d947ac8622932e63d8731733e4cf328b7d7401302fcc68ffa0d2ffcf30c' for r in case['records']),'mutations_exercised':False,'claim_limits':['The frozen captured control-data premise is explicit; no executed path or root cause is established.','Pinned resolver fixtures and this original Windows dump are exercised; no full R6 or release acceptance follows.']}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
selected=[p for p in out.rglob('*') if p.is_file() and p.suffix not in ['.gz'] and p.name not in ['native-explanation.json','rust-explanation.json','bap-explanation.json']]
selected.extend(out.glob('*-explanation.json.gz'))
with tarfile.open(out/'evidence.tar.gz','w:gz') as archive:
 for p in selected:archive.add(p,arcname=str(p.relative_to(out)),recursive=False)
print(json.dumps({'evidence_bytes':(out/'evidence.tar.gz').stat().st_size,'evidence_sha256':hashlib.sha256((out/'evidence.tar.gz').read_bytes()).hexdigest(),'table_targets':len(dispatch['targets']),'state_records':case['records'],'explanation_equal':True}))
SEAL
printf '%s\n' 'DUMP RETRY COMPLETE'
