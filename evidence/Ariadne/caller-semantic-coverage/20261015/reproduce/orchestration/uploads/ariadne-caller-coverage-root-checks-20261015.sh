#!/bin/bash
set -euo pipefail
python3 /mnt/d/ariadne-caller-coverage-setup-20261015.py
external=/mnt/d/ariadne-caller-coverage-20261015
cp /mnt/d/ariadne-caller-coverage-root-checks-20261015.py "$external/root-checks.py"
chown jlc:jlc "$external/root-checks.py"
exec runuser -u jlc -- bash "$external/run.sh" python3 /caller-work/root-checks.py
