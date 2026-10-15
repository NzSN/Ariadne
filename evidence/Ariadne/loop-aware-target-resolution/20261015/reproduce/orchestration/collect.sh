#!/bin/bash
set -euo pipefail

# Invoke after validation/replay/dump producers have stopped. This does not
# resynchronize the source checkout or rerun any qualification gate.
external=/mnt/d/ariadne-loop-aware-20261015
test -f "$external/run.sh"
test -f "$external/source-manifest.json"
cp /mnt/d/ariadne-loop-aware-collect-20261015.py "$external/collect.py"
cp /mnt/d/ariadne-loop-aware-collect-20261015.sh "$external/collect.sh"
mkdir -p "$external/orchestration-inputs" "$external/inputs"
for source in /mnt/d/ariadne-loop-aware-*20261015.py \
              /mnt/d/ariadne-loop-aware-*20261015.sh \
              /mnt/d/ariadne-loop-aware-*20261015.rs; do
  if [[ -f "$source" ]]; then
    cp "$source" "$external/orchestration-inputs/$(basename "$source")"
  fi
done
python3 - <<'PY'
from pathlib import Path
import hashlib,json,shutil
task=Path('/mnt/d/ariadne-loop-aware-20261015')
record=json.loads((task/'source-manifest.json').read_text())
source=Path('/mnt/d/ariadne-loop-aware-source-20261015.tar.gz')
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()
if sha(source)!=record['archive_sha256']:
    raise SystemExit('uploaded source archive differs from current task manifest')
destination=task/'inputs'/('source-'+record['archive_sha256']+'.tar.gz')
if not destination.exists():
    shutil.copyfile(source,destination)
if sha(destination)!=record['archive_sha256']:
    raise SystemExit('retained source archive identity differs')
PY
chown -R jlc:jlc "$external/orchestration-inputs" "$external/inputs"
chown jlc:jlc "$external/collect.py" "$external/collect.sh"
exec runuser -u jlc -- bash "$external/run.sh" python3 /loop-work/collect.py
