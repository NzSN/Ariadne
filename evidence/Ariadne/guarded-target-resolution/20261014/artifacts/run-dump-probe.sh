#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
  base=/home/jlc/ariadne-p4-20261010
  out="$base/work/guarded-target-resolution-20261014"
  cp /mnt/d/ariadne-composed-dump-probe-20261014.rs "$out/dump-probe.rs"
  cp "$0" "$out/run-dump-probe.sh"
  chown jlc:jlc "$out/dump-probe.rs" "$out/run-dump-probe.sh"
  exec runuser -u jlc -- "$base/run.sh" bash /work/guarded-target-resolution-20261014/run-dump-probe.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-composed-20261014
export ARIADNE_BAP_CORE_DIR="$PWD/target/composed-native" ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc"
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift" BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
export ARIADNE_TARGET_DIAGNOSTICS=1
out=/work/guarded-target-resolution-20261014
dump=/work/frame-paths-dump03958-20261013/original.dmp
witness="$PWD/evidence/Ariadne/indirect-target-resolution/dump03958-table-witness-20261014/tables.json"
baseline=/work/native-request-budget-20261014/probe-expanded/guard-report.json
printf '%s\n' "9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab  $dump" \
  "1390abca21bb7e2db9cde9a07067f60f5493498a7866fb648dcb103994674baf  $witness" \
  "d0294c9b940d8366cb89d78a95d2186c89196dbf1a7955e70189c22afa2abda0  $baseline" | sha256sum --check
python3 - <<'PY'
from pathlib import Path
import os,subprocess
root=Path.cwd();out=Path('/work/guarded-target-resolution-20261014');build=root/'target/composed-build/release'
libs=list((build/'deps').glob('libserde_json-*.rlib'))
if not libs:raise SystemExit('release serde_json dependency missing')
subprocess.run(['rustc','--edition=2024',str(out/'dump-probe.rs'),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libs[0]),'-o',str(out/'dump-probe')],check=True,env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
PY
run="$out/dump-$(date -u +%Y%m%dT%H%M%S)"
mkdir -p "$run"
printf 'Original dump probe artifacts: %s\n' "$run"
/usr/bin/time -v timeout 900 "$out/dump-probe" "$dump" "$run" "$witness" "$baseline" paths \
  > "$run/probe.log" 2> "$run/timing.log"
cat "$run/probe.log"
