#!/usr/bin/env python3
"""Three native opaque-admission mutants with the existing unchanged observer."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path("/home/nzsn/Repos/Ariadne-caller-coverage-20261015")
OBSERVER = ROOT / "tests/input/bap_core.rs"
TOOL = ROOT / "tools/check_bap_mutations.py"
TEST = "native_rejects_opaque_contract_tampering_directly"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, environment, log, timeout=900):
    completed = subprocess.run([str(value) for value in command], cwd=ROOT, env=environment,
                               text=True, capture_output=True, timeout=timeout)
    log.write_text(completed.stdout + completed.stderr)
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cargo-target", type=Path, required=True)
    parser.add_argument("--native-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / "target"):
        raise SystemExit("mutant outputs must remain under the task checkout's target/")
    args.output.mkdir(parents=True, exist_ok=False)
    mutations = None
    for node in ast.walk(ast.parse(TOOL.read_text())):
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "native_mutants"
                                                for target in node.targets):
            mutations = ast.literal_eval(node.value)
    if mutations is None or len(mutations) != 3:
        raise RuntimeError("expected the exact three native capture mutations")
    original = (ROOT / "native/bap-core/capture.ml").read_text()
    for name, before, _ in mutations:
        if original.count(before) != 1:
            raise RuntimeError("nonunique native opaque mutation seam: " + name)
    observer = sha(OBSERVER)
    environment = {**os.environ, "ARIADNE_BAP_CORE_DIR": str(args.native_dir),
                   "CARGO_TARGET_DIR": str(args.cargo_target)}
    command = ["cargo", "test", "--offline", "--locked", "--test", "input_bap_core", TEST,
               "--", "--exact", "--ignored", "--nocapture"]
    baseline = run(command, environment, args.output / "baseline.log")
    if baseline.returncode or f"test {TEST} ... ok" not in baseline.stdout:
        raise RuntimeError("native opaque observer baseline did not pass")
    rows = []
    for name, before, after in mutations:
        work = args.output / name
        work.mkdir()
        source = work / "source"
        shutil.copytree(ROOT / "native/bap-core", source, ignore=shutil.ignore_patterns("__pycache__"))
        (source / "capture.ml").write_text(original.replace(before, after))
        helper = work / "helper"
        built = run(["python3", ROOT / "native/bap-core/build.py", "--source-dir", source, "--output", helper],
                    environment, work / "compile.log")
        if built.returncode:
            raise RuntimeError("native opaque mutant compile failure earns no credit: " + name)
        tested = run(command, {**environment, "ARIADNE_BAP_CORE_DIR": str(helper)}, work / "observer.log")
        output = tested.stdout + tested.stderr
        marker = "native admitted opaque " + {
            "native-opaque-kill-accepted": "kill", "native-opaque-footprint-lost": "uses",
            "native-opaque-profile-ignored": "profile"}[name] + " mutation"
        credit = (tested.returncode == 101 and f"test {TEST} ... FAILED" in output
                  and marker in output and "could not compile" not in output)
        rows.append({"name": name, "behavioral_credit": credit, "expected_failure_marker": marker,
                     "source_sha256": sha(source / "capture.ml"),
                     "helper_sha256": sha(helper / "ariadne-bap-core"),
                     "helper_manifest_sha256": sha(helper / "manifest.json"),
                     "exit_code": tested.returncode})
        print(name, "CREDIT" if credit else "FAIL", flush=True)
    result = {"schema": "ariadne.caller-native-opaque-mutations/v1", "passed": all(row["behavioral_credit"] for row in rows),
              "baseline_passed": True, "observer_unchanged": observer == sha(OBSERVER),
              "observer_sha256": observer, "repository_mutation_tool_sha256": sha(TOOL),
              "driver_sha256": sha(Path(__file__)), "mutants": rows}
    result["passed"] &= result["observer_unchanged"]
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
