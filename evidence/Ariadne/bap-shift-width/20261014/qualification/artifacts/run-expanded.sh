#!/bin/bash
set -euo pipefail
if [[ ${1:-} != --inside ]]; then
 base=/home/jlc/ariadne-p4-20261010
 out="$base/work/bap-shift-width-20261014"
 cp "$0" "$out/run-expanded.sh"
 cp /mnt/d/ariadne-shift-expanded-probe-20261014.rs "$out/expanded_probe.rs"
 chown jlc:jlc "$out/run-expanded.sh" "$out/expanded_probe.rs"
 exec runuser -u jlc -- "$base/run.sh" bash /work/bap-shift-width-20261014/run-expanded.sh --inside
fi
cd /home/nzsn/Repos/Ariadne-bap-shift-count-20261014
export CARGO_INCREMENTAL=0
export CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_BUILD_JOBS=2
export CARGO_TARGET_DIR="$PWD/target/shift-build"
export ARIADNE_BAP_CORE_DIR="$PWD/target/shift-native" ARIADNE_LLVM_MC="$PWD/target/ariadne-llvm-mc"
export ARIADNE_BAP_HELPER="$PWD/target/ariadne-bap-lift" BAP_RUNTIME_ROOT="$PWD/tmp/bap-setup/stable"
out=/work/bap-shift-width-20261014
dump=/work/frame-paths-dump03958-20261013/original.dmp
printf '%s\n' "9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab  $dump" | sha256sum --check
python3 - <<'INNER'
from pathlib import Path
import subprocess,os
root=Path.cwd();out=Path('/work/bap-shift-width-20261014');build=root/'target/shift-build/release'
libs=list((build/'deps').glob('libserde_json-*.rlib'))
subprocess.run(['rustc','--edition=2024',str(out/'expanded_probe.rs'),'-O','-L','dependency='+str(build/'deps'),'--extern','ariadne='+str(build/'libariadne.rlib'),'--extern','serde_json='+str(libs[0]),'-o',str(out/'expanded_probe')],check=True,env={**os.environ,'CARGO_MANIFEST_DIR':str(root)})
INNER
for mode in guarded; do
 /usr/bin/time -v timeout 1200 "$out/expanded_probe" "$dump" "$out/dump-expanded-$mode" "$mode" > "$out/dump-expanded-$mode.log" 2> "$out/dump-expanded-$mode-timing.log"
 cat "$out/dump-expanded-$mode.log"
done
