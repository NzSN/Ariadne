#!/usr/bin/env python3
"""Compile isolated native caller controls on the qualified remote WSL host.

Source-rule controls use immutable captured fixtures. Optional full wire files
come from Rust's public CoreAdapter/preparation exports. Mutation credit requires
the original positive to pass and the isolated semantic negative to be accepted;
compilation failures, crashes, missing cases and timeouts receive no credit.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native/bap-core"
DRIVER = ROOT / "tests/bap/caller_coverage_native.ml"
MUTANTS = [
    ("terminal-bytes", "terminal.ml", "terminal-int3", "terminal-bytes",
     'require(full="cc" && consumed=full',
     'require(true && consumed=full'),
    ("ud1-full-extent", "terminal.ml", "terminal-ud1", "ud1-extra-extent",
     'if !valid && !extent=length then Some(prefix,mode)else None',
     'if !valid && !extent<=length then Some(prefix,mode)else None'),
    ("terminal-source-bil", "terminal.ml", "terminal-int3", "terminal-extra-effect",
     '(match bil with `List[statement]->exact statement ["kind";"number"];\n'
     '        string statement "kind"="exception" && get statement "number"=`Int 3|_->false)',
     'true'),
    ("terminal-normal-successor", "terminal.ml", "terminal-int3", "terminal-normal-successor",
     'require(string source "site"=site && get source "bytes_hex"=get receipt "bytes_hex" &&',
     'require(true || string source "site"=site && get source "bytes_hex"=get receipt "bytes_hex" &&'),
    ("terminal-local-scope", "terminal.ml", "flow-original", "flow-unknown-scope",
     'string evidence "scope"="local-normal-completion/v1"', 'true'),
    ("load-preserved-vector-bank", "guard.ml", "movaps-load-original", "movaps-load-high-bank",
     'var_ref(get high "arg")("YMM"^string_of_int bank)256 "imm" &&', 'true &&'),
    ("proof-gated-normal-decode", "guard.ml", "stopped-guard-original", "stopped-guard-premature-decode",
     'require (not(S.mem site i.decodable) &&', 'require (true &&'),
    ("legacy-policy", "legacy_guard.ml", "legacy-store-original", "legacy-load-admitted",
     'let recognized site =\n  try',
     'let recognized site =\n'
     '  if String.length(string site "bytes_hex")>=4 &&\n'
     '    String.sub(string site "bytes_hex")0 4="0f28" then Some(0L,6,`Null) else\n'
     '  try'),
]
WIRE_MUTANTS = [
    ("terminal-conservative-effects", "guard.ml", "wire-int3", "wire-terminal-narrowed-uses-int3",
     'S.equal instruction.uses i.locations && S.equal instruction.may i.locations &&',
     'true && S.equal instruction.may i.locations &&'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, directory, environment, log):
    try:
        result = subprocess.run(args, cwd=directory, env=environment,
                                text=True, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired as error:
        log.write_text(str(error) + "\n")
        return False
    log.write_text(result.stdout + result.stderr)
    return result.returncode == 0


def build(directory, native, environment, compiler, mutation=None):
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DRIVER, directory / DRIVER.name)
    selected = {}
    if mutation:
        filename, replacement = mutation
        (directory / filename).write_text(replacement)
        sources = [filename]
        if filename in {"terminal.ml", "legacy_guard.ml"}:
            # Guard imports Terminal's implementation, so rebuild this dependent
            # in the same isolated directory before linking a Terminal mutant.
            shutil.copyfile(NATIVE / "guard.ml", directory / "guard.ml")
            sources.append("guard.ml")
        for source in sources:
            args = [str(compiler), "ocamlopt", "-package", "bap,yojson",
                    "-I", str(directory), "-I", str(native), "-c", source]
            if not command(args, directory, environment, directory / (source + ".compile.log")):
                return None
            selected[Path(source).stem] = directory / (Path(source).stem + ".cmx")
    args = [str(compiler), "ocamlopt", "-linkpkg", "-package", "bap,yojson",
            "-I", str(directory), "-I", str(native), "-o", "caller-checker"]
    args.extend(str(selected.get(name, native / (name + ".cmx"))) for name in
                ("build_identity", "recovery", "terminal", "legacy_capture", "capture",
                 "legacy_guard", "guard"))
    args.append(DRIVER.name)
    if not command(args, directory, environment, directory / "driver.compile.log"):
        return None
    return directory / "caller-checker"


def observe(binary, environment, directory, label, case=None):
    args = [str(binary)] + (["--case", case] if case else [])
    try:
        completed = subprocess.run(args, env=environment, text=True,
                                   capture_output=True, timeout=120)
    except subprocess.TimeoutExpired as error:
        return {"status": "timeout", "error": str(error)}
    (directory / (label + ".stdout")).write_text(completed.stdout)
    (directory / (label + ".stderr")).write_text(completed.stderr)
    try:
        rows = json.loads(completed.stdout)
        if not isinstance(rows, list) or not rows:
            raise ValueError("missing native observations")
        if case and (len(rows) != 1 or rows[0]["case"] != case):
            raise ValueError("missing selected native control")
        for row in rows:
            if not all(isinstance(row[key], bool) for key in ("accepted", "expected", "passed")):
                raise ValueError("untyped native observation")
    except (ValueError, KeyError, TypeError) as error:
        return {"status": "invalid-output", "returncode": completed.returncode,
                "error": str(error)}
    return {"status": "observed", "returncode": completed.returncode, "rows": rows}


def protocol_observe(helper, wire, environment, directory, label, expected):
    """Exercise production main.ml admission, including actual initialization."""
    snapshot, profile = wire["capture"]["snapshot"], "captured-guarded-input/v2"
    canonical = json.dumps(wire, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    query_hash = hashlib.sha256(b"ariadne.bap-core-query/v1\0")
    for field in (snapshot.encode(), b"recovery", profile.encode(), canonical):
        query_hash.update(len(field).to_bytes(8, "big"))
        query_hash.update(field)
    query = query_hash.hexdigest()
    request = dict(schema="ariadne.bap-core/v1", session="caller-controls", snapshot=snapshot,
                   query=query, family="recovery", sequence=0, operation="initialize",
                   payload=dict(profile=profile, input=wire))
    # Preserve the actual carrier key order, especially reordered positives.
    frame = json.dumps(request, separators=(",", ":"), ensure_ascii=False) + "\n"
    reset = dict(request, sequence=1, operation="reset", payload={})
    try:
        completed = subprocess.run(
            [str(helper), "caller-controls", snapshot, query, "recovery", "--max-request-bytes",
             str(len(frame.encode()) + 1)],
            input=frame + json.dumps(reset, separators=(",", ":")) + "\n",
            env=environment, text=True, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired as error:
        return {"case": label, "status": "timeout", "passed": False, "error": str(error)}
    (directory / (label + ".stdout")).write_text(completed.stdout)
    (directory / (label + ".stderr")).write_text(completed.stderr)
    try:
        lines = [json.loads(line) for line in completed.stdout.splitlines()]
        ready, response = lines[:2]
        if profile not in ready["profiles"] or response["sequence"] != 0:
            raise ValueError("wrong ready capability or admission response")
        accepted = response.get("error") is None
        if accepted and (len(lines) != 3 or lines[2].get("sequence") != 1
                         or lines[2].get("error") is not None or completed.returncode != 0):
            raise ValueError("accepted input did not cleanly initialize and reset")
        if not accepted and response.get("error", {}).get("kind") != "semantic":
            raise ValueError("negative did not produce a semantic admission rejection")
        return {"case": label, "status": "observed", "expected": expected, "accepted": accepted,
                "passed": accepted == expected, "error": response.get("error"),
                "returncode": completed.returncode}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return {"case": label, "status": "invalid-output", "passed": False, "error": str(error),
                "returncode": completed.returncode}


def reordered(value):
    if isinstance(value, dict):
        return {key: reordered(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reordered(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wire-dir", type=Path)
    parser.add_argument("--receipt-dir", type=Path)
    parser.add_argument("--mutations", action="store_true")
    args = parser.parse_args()
    native, output = args.native_dir.resolve(), args.output.resolve()
    if not output.is_relative_to(ROOT / "target"):
        raise SystemExit("native checker builds must be isolated under target/")
    output.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("caller_native_sdk", NATIVE / "setup-sdk.py")
    sdk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sdk)
    environment = sdk.environment()
    environment["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    environment["ARIADNE_CALLER_SOURCE_ROOT"] = str(ROOT)
    if args.wire_dir:
        for name in ("int3", "ud2", "ud1"):
            if not (args.wire_dir / (name + "-guarded-wire.json")).is_file():
                raise SystemExit("requested wire controls require all three terminal exports")
        environment["ARIADNE_CALLER_WIRE_DIR"] = str(args.wire_dir.resolve())
    else:
        environment.pop("ARIADNE_CALLER_WIRE_DIR", None)
    if args.receipt_dir:
        environment["ARIADNE_CALLER_RECEIPT_DIR"] = str(args.receipt_dir.resolve())
    else:
        environment.pop("ARIADNE_CALLER_RECEIPT_DIR", None)
    compiler = sdk.PREFIX / "bin/ocamlfind"
    result = {
        "schema": "ariadne.native-caller-checker-controls/v1",
        "scope": "Source-rule and optional captured-wire checker controls; original dump retry is separate.",
        "driver_sha256": sha(DRIVER), "runner_sha256": sha(Path(__file__)),
        "source_sha256": {name: sha(NATIVE / name) for name in ("terminal.ml", "guard.ml", "legacy_guard.ml")},
        "native_manifest_sha256": sha(native / "manifest.json"),
        "fixtures": {str(path.relative_to(ROOT)): sha(path) for path in
                     sorted((ROOT / "tests/bap/fixtures/caller-coverage").glob("*.json"))},
        "wire_inputs": {path.name: sha(path) for path in sorted(args.wire_dir.glob("*-guarded-wire.json"))}
        if args.wire_dir else {},
        "receipt_inputs": {path.name: sha(path) for path in sorted(args.receipt_dir.glob("*-unit.json"))}
        if args.receipt_dir else {},
        "mutants": [],
    }
    binary = build(output / "baseline", native, environment, compiler)
    baseline = {"status": "compile-failed"} if binary is None else observe(
        binary, environment, output / "baseline", "controls")
    result["baseline"] = baseline
    passed = (baseline.get("status") == "observed" and baseline.get("returncode") == 0
              and all(row["passed"] for row in baseline["rows"]))
    result["production_protocol"] = []
    if passed and args.wire_dir:
        files = sorted(args.wire_dir.glob("*-guarded-wire.json"))
        if not files:
            raise SystemExit("requested wire directory contains no captured wire exports")
        protocol_directory = output / "production-protocol"
        protocol_directory.mkdir(exist_ok=True)
        for path in files:
            wire, name = json.loads(path.read_text()), path.stem
            variants = [(name, wire, True), (name + "-reordered", reordered(wire), True)]
            null_flow = copy.deepcopy(wire)
            null_flow["guard_admission"]["input"]["normal_flow"] = None
            variants.append((name + "-null-flow", null_flow, False))
            legacy = copy.deepcopy(wire)
            legacy["guard_admission"]["schema"] = "ariadne.guard-admission/v1"
            variants.append((name + "-legacy-schema", legacy, False))
            for label, value, expected in variants:
                result["production_protocol"].append(protocol_observe(
                    native / "ariadne-bap-core", value, environment, protocol_directory, label, expected))
        passed = all(row["passed"] for row in result["production_protocol"])
    if passed and args.mutations:
        for name, filename, positive_case, negative_case, before, after in (
                MUTANTS + (WIRE_MUTANTS if args.wire_dir else [])):
            original = (NATIVE / filename).read_text()
            if original.count(before) != 1:
                raise SystemExit("mutation seam is not unique: " + name)
            changed = original.replace(before, after)
            directory = output / name
            mutant = {"name": name, "module": filename, "positive_case": positive_case,
                      "negative_case": negative_case, "source_sha256": hashlib.sha256(changed.encode()).hexdigest(),
                      "behavioral_credit": False}
            altered = build(directory, native, environment, compiler, (filename, changed))
            if altered is None:
                mutant["status"] = "compile-failed"
            else:
                positive = observe(altered, environment, directory, "positive", positive_case)
                negative = observe(altered, environment, directory, "negative", negative_case)
                mutant.update(status="observed", positive=positive, negative=negative)
                mutant["behavioral_credit"] = (
                    positive.get("status") == negative.get("status") == "observed"
                    and positive.get("returncode") == 0
                    and positive["rows"][0]["accepted"] is True
                    and negative.get("returncode") == 1
                    and negative["rows"][0]["accepted"] is True
                    and negative["rows"][0]["passed"] is False)
            result["mutants"].append(mutant)
        passed = all(row["behavioral_credit"] for row in result["mutants"])
    result["passed"] = passed
    result["behavioral_mutant_credits"] = sum(row["behavioral_credit"] for row in result["mutants"])
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": passed, "controls": len(baseline.get("rows", [])),
                      "mutants": len(result["mutants"]),
                      "behavioral_mutant_credits": result["behavioral_mutant_credits"]}))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
