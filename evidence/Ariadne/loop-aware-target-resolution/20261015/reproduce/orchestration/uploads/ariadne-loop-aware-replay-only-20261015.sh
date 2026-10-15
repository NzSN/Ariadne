#!/bin/bash
set -euo pipefail

# setup-remote.py must already have populated the exact source snapshot.
# Run only after the final native build, so helper identity stays immutable.
external=/mnt/d/ariadne-loop-aware-20261015
test -f "$external/run.sh"
test -f "$external/source-manifest.json"
cp /mnt/d/ariadne-loop-aware-replay-only-20261015.py "$external/replay-only.py"
chown jlc:jlc "$external/replay-only.py"
exec runuser -u jlc -- bash "$external/run.sh" python3 /loop-work/replay-only.py
