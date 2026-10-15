#!/bin/bash
set -euo pipefail
python3 /mnt/d/ariadne-caller-coverage-setup-final-20261015.py
external=/mnt/d/ariadne-caller-coverage-20261015
cp /mnt/d/ariadne-caller-coverage-final-checks-20261015.py "$external/final-checks.py"
chown jlc:jlc "$external/final-checks.py"
exec runuser -u jlc -- bash "$external/run.sh" python3 /caller-work/final-checks.py
