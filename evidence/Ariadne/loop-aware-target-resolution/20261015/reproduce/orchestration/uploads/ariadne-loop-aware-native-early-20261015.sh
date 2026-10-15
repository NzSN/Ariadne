#!/bin/bash
set -euo pipefail
external=/mnt/d/ariadne-loop-aware-20261015
log="$external/evidence/native-controls-early-$(date -u +%Y%m%dT%H%M%S).log"
status=0
runuser -u jlc -- bash "$external/run.sh" python3 tests/bap/newloop_native_controls.py \
  --native-dir target/loop-aware-native \
  --receipt-dir /loop-work/evidence/early-20261015T043139/loop-receipts \
  --output target/loop-aware-native-controls-early --mutations > "$log" 2>&1 || status=$?
cat "$log"
exit "$status"
