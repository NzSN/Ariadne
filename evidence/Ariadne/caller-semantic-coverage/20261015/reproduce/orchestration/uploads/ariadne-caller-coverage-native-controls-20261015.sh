#!/bin/bash
set -euo pipefail
external=/mnt/d/ariadne-caller-coverage-20261015
cp /mnt/d/ariadne-caller-coverage-native-controls-20261015.py "$external/native-controls.py"
chown jlc:jlc "$external/native-controls.py"
exec runuser -u jlc -- bash "$external/run.sh" python3 /caller-work/native-controls.py
