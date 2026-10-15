#!/usr/bin/env python3
"""Full legacy guard v7/v8 controls and one dependency-reversion mutant.

Run only on the qualified remote SDK host. The source bytes/BIL come from the
retained real BAP combined fixture. Its first ordinary transfer is widened to
opaque and all RSP facts conservatively widened; guard normal effects are then
withdrawn. Changing only that capture row's projection to v8 must be rejected.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "tests/bap/legacy_guard_capture.ml"
SOURCE = ROOT / "native/bap-core/legacy_guard.ml"
FIXTURE = ROOT / "evidence/Ariadne/loop-aware-target-resolution/20261015/artifacts/validation-20261015T050857/passing-combined-wire.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mutations", action="store_true")
    args = parser.parse_args()
    native, output = args.native_dir.resolve(), args.output.resolve()
    if not output.is_relative_to(ROOT / "target"):
        raise SystemExit("legacy native checker outputs must remain under target/")
    output.mkdir(parents=True, exist_ok=False)
    unit = module("legacy_capture_native_unit", ROOT / "tests/bap/caller_coverage_native_controls.py")
    unit.DRIVER = DRIVER
    sdk = module("legacy_capture_native_sdk", ROOT / "native/bap-core/setup-sdk.py")
    environment = sdk.environment()
    environment["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    environment["ARIADNE_CALLER_SOURCE_ROOT"] = str(ROOT)
    compiler = sdk.PREFIX / "bin/ocamlfind"
    result = {"schema": "ariadne.legacy-guard-capture-dependency-controls/v1",
              "scope": "Full Legacy_guard.admit, conservative widening of an actual retained source-bound BAP fixture.",
              "source_sha256": sha(SOURCE), "driver_sha256": sha(DRIVER),
              "runner_sha256": sha(Path(__file__)), "fixture_sha256": sha(FIXTURE),
              "native_manifest_sha256": sha(native / "manifest.json"), "mutants": []}
    binary = unit.build(output / "baseline", native, environment, compiler)
    baseline = {"status": "compile-failed"} if binary is None else unit.observe(
        binary, environment, output / "baseline", "controls")
    result["baseline"] = baseline
    passed = (baseline.get("status") == "observed" and baseline.get("returncode") == 0
              and len(baseline["rows"]) == 2 and all(row["passed"] for row in baseline["rows"]))
    if passed and args.mutations:
        original = SOURCE.read_text()
        before, after = "let i,capture_sites=Legacy_capture.admit", "let i,capture_sites=Capture.admit"
        if original.count(before) != 1:
            raise RuntimeError("legacy capture dependency mutation seam must be unique")
        changed = original.replace(before, after)
        directory = output / "restore-current-capture-dependency"
        altered = unit.build(directory, native, environment, compiler, ("legacy_guard.ml", changed))
        mutant = {"name": "restore-current-capture-dependency", "behavioral_credit": False,
                  "source_sha256": hashlib.sha256(changed.encode()).hexdigest()}
        if altered is None:
            mutant["status"] = "compile-failed"
        else:
            positive = unit.observe(altered, environment, directory, "positive", "legacy-opaque-v7")
            negative = unit.observe(altered, environment, directory, "negative", "legacy-opaque-v8")
            mutant.update(status="observed", positive=positive, negative=negative)
            mutant["behavioral_credit"] = (
                positive.get("status") == negative.get("status") == "observed"
                and positive.get("returncode") == 0 and positive["rows"][0]["accepted"] is True
                and negative.get("returncode") == 1 and negative["rows"][0]["accepted"] is True
                and negative["rows"][0]["passed"] is False)
        result["mutants"].append(mutant)
        passed = mutant["behavioral_credit"]
    result["passed"] = passed
    result["behavioral_mutant_credits"] = sum(row["behavioral_credit"] for row in result["mutants"])
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": passed, "controls": len(baseline.get("rows", [])),
                      "behavioral_mutant_credits": result["behavioral_mutant_credits"]}))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
