#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
run_root=${FRAME_QUESTION_MODEL_OUT:-$repo_root/target/frame-question-model}
mkdir -p "$run_root"
python3 - "$repo_root" "$run_root/source-before.json" <<'PYHASH'
import hashlib,json,sys
from pathlib import Path
r=Path(sys.argv[1]);paths=[r/'Specs/AriadneFrameQuestion.tla',r/'Specs/AriadneQuestionSchedule.tla',r/'Specs/check-frame-question.sh',*sorted((r/'Specs').glob('FrameQuestion*.cfg')),*sorted((r/'Specs').glob('QuestionSchedule*.cfg'))]
Path(sys.argv[2]).write_text(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n')
PYHASH
cd "$repo_root/Specs"
for model in AriadneQuestionSchedule AriadneFrameQuestion; do
  "${APALACHE_MC:-apalache-mc}" --out-dir="$run_root/typecheck-$model" typecheck "$model.tla" > "$run_root/$model-typecheck.log" 2>&1
done
for cfg in QuestionSchedule*.cfg FrameQuestion*.cfg; do
  model=AriadneFrameQuestion
  [[ $cfg == QuestionSchedule* ]] && model=AriadneQuestionSchedule
  "${TLC:-tlc}" -workers 1 -metadir "$run_root/${cfg%.cfg}" -config "$cfg" "$model.tla" > "$run_root/${cfg%.cfg}.log" 2>&1
  rg -q 'Model checking completed. No error has been found.' "$run_root/${cfg%.cfg}.log"
done
python3 - "$repo_root" "$run_root" <<'PYHASH'
import hashlib,json,sys
from pathlib import Path
r,o=map(Path,sys.argv[1:]);before=json.loads((o/'source-before.json').read_text());after={p:hashlib.sha256((r/p).read_bytes()).hexdigest() for p in before};(o/'source-stability.json').write_text(json.dumps({'unchanged':before==after,'sources':after},indent=2)+'\n');assert before==after
PYHASH
printf 'Frame question models: typecheck, safety and fair termination passed.\n'
