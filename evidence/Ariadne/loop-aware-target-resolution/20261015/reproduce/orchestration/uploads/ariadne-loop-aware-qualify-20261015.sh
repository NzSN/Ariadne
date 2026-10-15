#!/bin/bash
set -euo pipefail
python3 /mnt/d/ariadne-loop-aware-setup-20261015.py
external=/mnt/d/ariadne-loop-aware-20261015
cp /mnt/d/ariadne-loop-aware-qualify-20261015.py "$external/qualify.py"
cp /mnt/d/ariadne-loop-aware-local-documentation-20261015.json "$external/local-documentation.json"
chown jlc:jlc "$external/qualify.py" "$external/local-documentation.json"
exec runuser -u jlc -- bash "$external/run.sh" python3 /loop-work/qualify.py
