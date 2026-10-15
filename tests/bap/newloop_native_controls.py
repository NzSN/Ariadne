#!/usr/bin/env python3
"""Run native loop-checker controls and isolated semantic source mutations.

Compile/run this only on the qualified remote WSL SDK host. The input reports
come from ARIADNE_LOOP_RECEIPT_DIR exports of the Rust dump-fixture unit test.
Compilation failures, timeouts, and malformed output never earn mutation credit.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "native/bap-core/loop_closure.ml"
DRIVER = ROOT / "tests/bap/newloop_receipt.ml"
MUTANTS = [
    ("edge-inventory", "internal",
     "require((internal,incoming,exits)=",
     "require(true || (internal,incoming,exits)="),
    ("source-reference-inventory", "bytes",
     'require(same(`List expected_sources)(get receipt "source_refs"))',
     'require(true || same(`List expected_sources)(get receipt "source_refs"))'),
    ("entrance-inclusion", "entrance-state",
     'require(included work state(M.find to_ assertions)) "loop entrance inclusion"',
     'require(true || included work state(M.find to_ assertions)) "loop entrance inclusion"'),
    ("base-preservation", "base-preservation-state",
     'require(included work state(M.find to_ assertions)) "loop preservation inclusion"',
     'require(true || included work state(M.find to_ assertions)) "loop preservation inclusion"'),
    ("branch-provenance", "branch-definition",
     '  M.for_all(fun key term->match M.find_opt key actual.flags with\n    Some value->same value term|None->false) expected.flags',
     '  true (* mutation: omit branch-definition provenance *)'),
    ("successor-coverage", "extra-dispatch-successor",
     'require(S.equal derived instruction.targets && S.equal derived(set ~addr:true(get row "targets")))',
     'require(true || (S.equal derived instruction.targets && S.equal derived(set ~addr:true(get row "targets"))))'),
    ("selector-freshness", "fresh-selector-state",
     'if width=8 || width=16 then top width',
     'if width=8 then constant width 0L else if width=16 then top width'),
    ("candidate-epoch-binding", "stale-candidate-epoch",
     '    get receipt "graph_sha256"=get report "graph_sha256" &&\n',
     ''),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_sdk():
    spec = importlib.util.spec_from_file_location(
        "loop_checker_sdk", ROOT / "native/bap-core/setup-sdk.py")
    sdk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sdk)
    return sdk


def run_command(command, directory, environment, log):
    try:
        result = subprocess.run(command, cwd=directory, env=environment, text=True,
                                capture_output=True, timeout=120)
    except subprocess.TimeoutExpired as error:
        log.write_text(str(error) + "\n")
        return False
    log.write_text(result.stdout + result.stderr)
    return result.returncode == 0


def build(directory, native, environment, compiler, replacement=None):
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DRIVER, directory / DRIVER.name)
    module = native / "loop_closure.cmx"
    include = []
    if replacement is not None:
        (directory / SOURCE.name).write_text(replacement)
        command = [str(compiler), "ocamlopt", "-package", "bap,yojson",
                   "-I", str(native), "-c", SOURCE.name]
        if not run_command(command, directory, environment, directory / "compile-module.log"):
            return None
        module = directory / "loop_closure.cmx"
        include = ["-I", str(directory)]
    command = [str(compiler), "ocamlopt", "-linkpkg", "-package", "bap,yojson",
               *include, "-I", str(native), "-o", "newloop-checker"]
    command.extend(str(native / (name + ".cmx")) for name in
                   ("build_identity", "recovery", "legacy_capture", "capture", "guard"))
    command.extend([str(module), DRIVER.name])
    if not run_command(command, directory, environment, directory / "compile-driver.log"):
        return None
    return directory / "newloop-checker"


def observe(binary, environment, directory, name, case=None):
    command = [str(binary)] + (["--case", case] if case else [])
    try:
        result = subprocess.run(command, env=environment, text=True,
                                capture_output=True, timeout=120)
    except subprocess.TimeoutExpired as error:
        return {"status": "timeout", "error": str(error)}
    (directory / (name + ".stdout")).write_text(result.stdout)
    (directory / (name + ".stderr")).write_text(result.stderr)
    try:
        rows = json.loads(result.stdout)
        if not isinstance(rows, list) or not rows:
            raise ValueError("missing checker observations")
        if case and (len(rows) != 1 or rows[0]["case"] != case):
            raise ValueError("wrong checker observation")
    except (ValueError, KeyError) as error:
        return {"status": "invalid-output", "error": str(error),
                "returncode": result.returncode}
    return {"status": "observed", "returncode": result.returncode, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mutations", action="store_true")
    args = parser.parse_args()
    native, output = args.native_dir.resolve(), args.output.resolve()
    if not output.is_relative_to(ROOT / "target"):
        raise SystemExit("checker builds must be isolated under target/")
    output.mkdir(parents=True, exist_ok=True)
    sdk = load_sdk()
    environment = sdk.environment()
    environment["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    environment["ARIADNE_LOOP_RECEIPT_DIR"] = str(args.receipt_dir.resolve())
    compiler = sdk.PREFIX / "bin/ocamlfind"
    result = {
        "schema": "ariadne.native-loop-checker-controls/v1",
        "scope": "Independent native checker units over Rust-exported fixtures; production paired admission is separate.",
        "source_sha256": sha(SOURCE), "driver_sha256": sha(DRIVER),
        "native_manifest_sha256": sha(native / "manifest.json"),
        "inputs": {path.name: sha(path) for path in sorted(args.receipt_dir.glob("*.json"))},
        "mutants": [],
    }
    binary = build(output / "baseline", native, environment, compiler)
    result["baseline"] = {"status": "compile-failed"} if binary is None else observe(
        binary, environment, output / "baseline", "controls")
    baseline = result["baseline"]
    passed = (baseline.get("status") == "observed" and baseline.get("returncode") == 0
              and all(row["passed"] for row in baseline["rows"]))
    if passed and args.mutations:
        original = SOURCE.read_text()
        for name, case, before, after in MUTANTS:
            if original.count(before) != 1:
                raise SystemExit("mutation seam is not unique: " + name)
            altered = original.replace(before, after)
            directory = output / name
            mutant = {"name": name, "negative_case": case,
                      "source_sha256": hashlib.sha256(altered.encode()).hexdigest(),
                      "behavioral_credit": False}
            changed = build(directory, native, environment, compiler, altered)
            if changed is None:
                mutant["status"] = "compile-failed"
            else:
                positive = observe(changed, environment, directory, "positive", "da09-original")
                negative = observe(changed, environment, directory, "negative", case)
                mutant.update(status="observed", positive=positive, negative=negative)
                mutant["behavioral_credit"] = (
                    positive.get("status") == negative.get("status") == "observed"
                    and positive.get("returncode") == 0
                    and positive["rows"][0]["accepted"] is True
                    and negative.get("returncode") == 1
                    and negative["rows"][0]["accepted"] is True
                    and negative["rows"][0]["passed"] is False)
            result["mutants"].append(mutant)
        passed = all(mutant["behavioral_credit"] for mutant in result["mutants"])
    result["passed"] = passed
    result["behavioral_mutant_credits"] = sum(
        mutant["behavioral_credit"] for mutant in result["mutants"])
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": passed, "controls": len(baseline.get("rows", [])),
                      "mutants": len(result["mutants"]),
                      "behavioral_mutant_credits": result["behavioral_mutant_credits"]}))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
