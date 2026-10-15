#!/bin/bash
set -euo pipefail
python3 /mnt/d/ariadne-loop-aware-setup-20261015.py
exec runuser -u jlc -- bash /mnt/d/ariadne-loop-aware-20261015/run.sh python3 /loop-work/early.py
