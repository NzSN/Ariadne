#!/bin/bash
set -euo pipefail
external=/mnt/d/ariadne-caller-coverage-20261015
mkdir -p "$external/qualification-continuation"
tar -xzf /mnt/d/ariadne-caller-qualification-continuation-20261015.tar.gz -C "$external/qualification-continuation"
chown -R jlc:jlc "$external/qualification-continuation"
exec runuser -u jlc -- bash "$external/run.sh" python3 /caller-work/qualification-continuation/qualify.py --early-evidence /caller-work/evidence/native-feedback-20261015T072430 --model-evidence /caller-work/evidence/early-20261015T070419 --native-controls-result /caller-work/evidence/native-controls-20261015T072536/native-controls/result.json --root-evidence /caller-work/evidence/root-checks-20261015T072948 --skip-native-capture --retained-prefix /caller-work/evidence/qualification-20261015T073307Z-11779
