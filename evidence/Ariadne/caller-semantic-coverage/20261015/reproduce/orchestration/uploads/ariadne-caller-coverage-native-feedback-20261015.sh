#!/bin/bash
set -euo pipefail
external=/mnt/d/ariadne-caller-coverage-20261015
cp /mnt/d/ariadne-caller-coverage-native-feedback-20261015.py "$external/native-feedback.py"
chown jlc:jlc "$external/native-feedback.py"
exec runuser -u jlc -- bash "$external/run.sh" python3 /caller-work/native-feedback.py
