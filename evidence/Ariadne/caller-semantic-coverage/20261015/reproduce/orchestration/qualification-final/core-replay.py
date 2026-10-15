#!/usr/bin/env python3
"""Task-private native 330-observation replay with an explicit build directory.

Uses the repository's unchanged model/corpus/binding preparation and observers.
Only orchestration and target selection are task-private.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path("/home/nzsn/Repos/Ariadne-caller-coverage-20261015")
sys.path.insert(0, str(ROOT / "mbt"))
from tools import FIXTURES, mirrors_tools, prepare_model, sha256, verify_corpus
from binding import check_binding


def run(command, output, environment=None):
    completed = subprocess.run([str(value) for value in command], cwd=ROOT, env=environment,
                               text=True, capture_output=True, timeout=600)
    output.write_text(completed.stdout + completed.stderr)
    if completed.returncode:
        raise RuntimeError("replay command failed: " + str(output))
    return completed.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper-dir", type=Path, required=True)
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    _, compiler, mirror = mirrors_tools()
    verify_corpus()
    core_model = prepare_model(args.output)
    check_binding(compiler, core_model, args.output / "core-binding.log")
    sys.path.insert(0, str(ROOT / "mbt/stage-e"))
    spec = importlib.util.spec_from_file_location("caller_stateflow_prepare", ROOT / "mbt/stage-e/prepare.py")
    stage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stage)
    stage_work = args.output / "stateflow"
    stage_work.mkdir()
    stateflow_model = stage.prepare_model(stage_work) / "MachineStateReplay.tla"
    manifest = json.loads((ROOT / "mbt/stage-e/corpus/manifest.json").read_text())
    for key, base in (("artifacts", ROOT / "mbt/stage-e"), ("oracleSources", ROOT)):
        for path, identity in manifest[key].items():
            if sha256(base / path) != identity:
                raise RuntimeError("stale stateflow corpus: " + path)
    run(["cargo", "build", "--offline", "--locked", "--no-default-features", "--features", "mbt,bap",
         "--bin", "ariadne-mbt", "--bin", "ariadne-stage-e-mbt", "--target-dir", args.target_dir],
        args.output / "build.log")
    families = {
        "core": (args.target_dir / "debug/ariadne-mbt", [], core_model,
                 ROOT / "mbt/corpus/AriadneReplay.lock.json",
                 [ROOT / "mbt/corpus" / (name + ".itf.json") for name in FIXTURES] * 2, 168),
        "machine-state": (args.target_dir / "debug/ariadne-stage-e-mbt", ["machine-state"], stateflow_model,
                          ROOT / "mbt/stage-e/corpus/MachineStateReplay.lock.json",
                          [ROOT / "mbt/stage-e/corpus" / (name + ".itf.json")
                           for name in manifest["engines"]["MachineStateReplay"]] * 2, 162),
    }
    environment = {**os.environ, "ARIADNE_REPLAY_BACKEND": "bap",
                   "ARIADNE_BAP_CORE_DIR": str(args.helper_dir.resolve())}
    records = {}
    for family, (binary, prefix, model, lock, traces, expected) in families.items():
        for mode in ("good", "wrong-digest"):
            label = family + "-" + mode
            output = run([binary, *prefix, mode, mirror, model, lock, *traces],
                         args.output / (label + ".log"), environment)
            record = json.loads(output.splitlines()[-1])
            observed = expected if mode == "good" else 0
            if (record["analysisBackend"] != "bap" or not record["gatePassed"]
                    or record["observationsDispatched"] != observed):
                raise RuntimeError("native generated replay mismatch: " + label)
            record["executableSha256"] = sha256(binary)
            records[label] = record
            print(label, observed, flush=True)
    result = {"schema": "ariadne.caller-native-generated-replay/v1", "passed": True,
              "observations": 330, "wrong_digest_observations": 0, "reports": records,
              "driver_sha256": sha256(Path(__file__)),
              "repository_driver_sha256": sha256(ROOT / "tools/check_bap_core_replay.py"),
              "orchestration_difference": "Explicit isolated target; same corpus preparation, binding and native observer commands.",
              "helper_manifest_sha256": sha256(args.helper_dir / "manifest.json"),
              "compiler_sha256": sha256(compiler), "mirror_sha256": sha256(mirror),
              "core_corpus_sha256": sha256(ROOT / "mbt/corpus/manifest.json"),
              "stateflow_corpus_sha256": sha256(ROOT / "mbt/stage-e/corpus/manifest.json")}
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
