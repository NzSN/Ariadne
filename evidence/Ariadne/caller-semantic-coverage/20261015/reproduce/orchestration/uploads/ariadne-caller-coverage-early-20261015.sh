#!/bin/bash
set -euo pipefail
python3 /mnt/d/ariadne-caller-coverage-setup-20261015.py
external=/mnt/d/ariadne-caller-coverage-20261015
cp /mnt/d/ariadne-caller-coverage-early-20261015.py "$external/early.py"
chown jlc:jlc "$external/early.py"
exec runuser -u jlc -- bash "$external/run.sh" python3 /caller-work/early.py
