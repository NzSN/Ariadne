#!/bin/bash
set -euo pipefail
python3 /mnt/d/ariadne-caller-coverage-setup-20261015.py
external=/mnt/d/ariadne-caller-coverage-20261015
cp /mnt/d/ariadne-caller-coverage-model-only-20261015.py "$external/model-only.py"
chown jlc:jlc "$external/model-only.py"
exec runuser -u jlc -- bash "$external/run.sh" python3 /caller-work/model-only.py
