#!/bin/bash
set -euo pipefail
external=/mnt/d/ariadne-caller-coverage-20261015
mkdir -p "$external/inputs"
tar -xf /mnt/d/ariadne-caller-source-history-20261015.tar -C "$external/inputs"
chown -R jlc:jlc "$external/inputs"
