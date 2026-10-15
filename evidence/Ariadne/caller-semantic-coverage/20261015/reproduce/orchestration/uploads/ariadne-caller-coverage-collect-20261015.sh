#!/bin/bash
set -euo pipefail

# Run only after task producers stop. This does not resynchronize sources or
# repeat qualification. The exact retained source capsule is a required argument.
source_capsule=${1:?usage: collect.sh /caller-work/inputs/source-SHA256.tar.gz}
case "$source_capsule" in
  /caller-work/inputs/*) ;;
  *) printf 'Select the explicit capsule under /caller-work/inputs.\n' >&2; exit 2 ;;
esac
external=/mnt/d/ariadne-caller-coverage-20261015
test -f "$external/run.sh"
test -f "$external/source-manifest.json"
test -f "$external${source_capsule#/caller-work}"
cp /mnt/d/ariadne-caller-coverage-collect-20261015.py "$external/collect.py"
cp /mnt/d/ariadne-caller-coverage-collect-20261015.sh "$external/collect.sh"
mkdir -p "$external/orchestration-inputs"
for source in /mnt/d/ariadne-caller-*20261015.py \
              /mnt/d/ariadne-caller-*20261015.sh \
              /mnt/d/ariadne-caller-*20261015.rs \
              /mnt/d/ariadne-caller-*20261015.cpp; do
  if [[ -f "$source" ]]; then
    cp "$source" "$external/orchestration-inputs/$(basename "$source")"
  fi
done
chown -R jlc:jlc "$external/orchestration-inputs"
chown jlc:jlc "$external/collect.py" "$external/collect.sh"
exec runuser -u jlc -- bash "$external/run.sh" python3 /caller-work/collect.py \
  --source-archive "$source_capsule"
