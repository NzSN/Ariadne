#!/bin/bash
set -euo pipefail
external=/mnt/d/ariadne-caller-coverage-20261015
cp "$external/repo-final/target/caller-native/manifest.json" "$external/evidence/final-checks-20261015T074922/native-manifest.json"
mkdir -p "$external/qualification-final"
tar -xzf /mnt/d/ariadne-caller-qualification-final-20261015.tar.gz -C "$external/qualification-final"
chown -R jlc:jlc "$external/qualification-final"
chown jlc:jlc "$external/evidence/final-checks-20261015T074922/native-manifest.json"
exec runuser -u jlc -- bash "$external/run.sh" python3 /caller-work/qualification-final/qualify.py --early-evidence /caller-work/evidence/final-checks-20261015T074922 --model-evidence /caller-work/evidence/early-20261015T070419 --native-controls-result /caller-work/evidence/final-checks-20261015T074922/native-controls/result.json --root-evidence /caller-work/evidence/final-checks-20261015T074922 --capture-evidence /caller-work/evidence/final-checks-20261015T074922
