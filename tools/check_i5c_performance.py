#!/usr/bin/env python3
"""Collect or freshly validate each frozen I5c native performance workload.

No builds are launched here. Run with freshly built release binaries through
with_mirrorrust_snapshot.py. Codec calls are unmeasured and authenticate typed
report recomputation/presentation only; the independent raw oracle below owns
capture/operand observations. This gate grants timing, never full I5c or I4.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

from i5a_native_contract import (environment, native_manifest,
                                 sha, strict_json, validate_backend_receipt,
                                 validate_phase_rows)
from with_mirrorrust_snapshot import active_identity

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/input/fixtures/i5c"
PERFORMANCE = FIXTURES / "performance.json"
SCHEMA = "ariadne.i5c-performance/v1"
ASSESSMENT_SCHEMA = "ariadne.address-wrap-assessment/v1"
PROFILE = "windows-amd64-av-scalar-mov-base-displacement-wrap-v1"
FORMATS = ("txt", "json", "dot")
OUTPUT_NAMES = {"report." + fmt for fmt in FORMATS} | {
    "address-wrap-assessment." + fmt for fmt in FORMATS}
PHASE_FIELDS = (
    "artifact_sha256,run,binding_ns,assessment_ns,render_ns,total_ns,evidence,claims,"
    "conclusion,output_sha256,analysis_backend,analysis_profile,analysis_family,"
    "snapshot_id,query_id,backend_query,helper_sha256,manifest_sha256,entry,site,"
    "memory_access,max_evidence,max_claims,scope_id,content_id").split(",")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read_json(path):
    return strict_json(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def object_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def contract():
    frozen = read_json(PERFORMANCE)
    scalars = {"warmups": 1, "measuredRepeats": 5, "maxPhaseMedianMs": 10,
               "maxCliMedianMs": 1500, "maxEvidence": 64, "maxClaims": 64}
    require(frozen.get("schema") == "ariadne.i5c-performance-contract/v1", "wrong frozen contract schema")
    for key, value in scalars.items():
        require(type(frozen.get(key)) is int and frozen[key] == value, "changed frozen contract: " + key)
    fixtures = [form + "-upper" for form in ("mov32mi", "mov64mi32", "mov32rm", "mov64rm", "mov32mr", "mov64mr")]
    fixtures += ["mov32mi-negative-zero", "mov32mi-underflow", "indexed-zero", "missing-integer"]
    controlled = [recipe + "-" + mode for recipe in ("upper", "none", "negative", "indexed")
                  for mode in ("partial", "full")]
    require(frozen.get("fixtureCases") == fixtures and frozen.get("controlledCases") == controlled,
            "changed frozen workload inventory/order")
    require(frozen.get("independentI4BudgetsMs") == {"linux": 250, "windows": 2000}, "changed independent I4 contract")
    return frozen


def source_inventory():
    # Includes Rust, fixtures, oracles, native/model/replay and validator sources.
    # Use the same broad inventory as native qualification, never a timing subset.
    from check_bap_core import sources
    return sources()


def tool_inventory(executables):
    paths = {**executables,
             "bap-lifter": ROOT / "target/ariadne-bap-lift",
             "bap-runtime": ROOT / "tmp/bap-setup/stable/usr/local/lib/libbap.so.2.5.0",
             "native-helper": ROOT / "target/bap-core-native/ariadne-bap-core",
             "native-manifest": ROOT / "target/bap-core-native/manifest.json",
             "sdk-lock": ROOT / "native/bap-core/sdk.lock.json",
             "sdk-manifest": ROOT / "target/bap-core-sdk/sdk-manifest.json",
             "lifter-lock": ROOT / "native/bap/toolchain.lock.json",
             "python": Path(sys.executable).resolve()}
    return {name: {"path": str(Path(path).resolve()), "sha256": sha(path)}
            for name, path in sorted(paths.items())}


def cohort(sources, tools, dependency):
    return {"sourceCohortSha256": object_digest(sources),
            "toolCohortSha256": object_digest(tools), "qualificationEnvironment": dependency}


def load_oracle():
    path = ROOT / "tests/input/fixtures/make_i5c.py"
    spec = importlib.util.spec_from_file_location("i5c_frozen_integer_oracle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    frozen = module.artifacts()
    require(read_json(FIXTURES / "manifest.json") == frozen["manifest.json"], "frozen fixture oracle changed")
    require(read_json(PERFORMANCE) == frozen["performance.json"], "performance contract differs from frozen oracle")
    return module, {row["name"]: row for row in frozen["manifest.json"]["cases"]}


def fixture_cases():
    oracle, indexed = load_oracle()
    raw_manifest = read_json(FIXTURES / "dumps/manifest.json")
    raw_rows = {row["name"]: row for row in raw_manifest["cases"]}
    require(len(raw_rows) == len(raw_manifest["cases"]) == 114, "raw fixture inventory differs")
    cases = []
    for name in contract()["fixtureCases"]:
        row = indexed[name]
        dump = FIXTURES / "dumps" / (name + ".dmp")
        generated = oracle.build_synthetic_capture(row)
        require(dump.read_bytes() == generated and sha(dump) == raw_rows[name]["sha256"]
                and len(generated) == raw_rows[name]["bytes"], "raw fixture disagrees with independent builder: " + name)
        cases.append({"case": name, "dump": str(dump.resolve()), "artifactSha256": sha(dump),
                      "entry": row["site"], "site": row["site"], "oracle": row["expected"],
                      "rawObservation": row})
    return cases


def controlled_cases(configuration):
    sys.path.insert(0, str(ROOT / "native/crashpad-demo"))
    from inspect_i5c import inspect
    cases = []
    for name in contract()["controlledCases"]:
        folder = Path(configuration["captures"]) / name
        observed = inspect(folder, Path(configuration["build"]), configuration["expectedBuildSha256"])
        recipe, mode = name.split("-")
        require(observed["case"] == name and observed["recipe"] == recipe and observed["mode"] == mode,
                "controlled capture placed in wrong workload position")
        arithmetic = None
        if recipe != "indexed":
            math_result = observed["arithmetic"]
            base = observed["observed"]["rcx"]
            displacement = observed["instruction"]["signed_displacement"]
            arithmetic = {"base_register": "rcx", "base_value": base,
                          "signed_displacement": displacement,
                          "displacement_bits": f"0x{displacement % (1 << 64):016x}",
                          "sum_before_reduction": math_result["wide_sum_decimal"],
                          "wrap_kind": math_result["wrap_kind"],
                          "effective_address": math_result["effective_address"]}
        cases.append({"case": name, "dump": str((folder / "capture.dmp").resolve()),
                      "artifactSha256": observed["inputs"]["dump"]["sha256"],
                      "entry": observed["query"]["entry"], "site": observed["query"]["site"],
                      "oracle": {"conclusion": observed["expectedConclusion"], "arithmetic": arithmetic,
                                 "truncated": False, "inputs_complete": True}, "rawObservation": observed})
    return cases


def raw_cases(configuration):
    return fixture_cases() + (controlled_cases(configuration) if configuration is not None else [])


def files_under(directory):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), "missing or symlinked evidence directory")
    result = {}
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), "symlink in raw evidence closure")
        if path.is_file():
            result[str(path.relative_to(directory))] = {"sha256": sha(path), "bytes": path.stat().st_size}
    return result


def run(command, destination, *, binding, timeout=120):
    """Ordinary bounded subprocess; receipts retain raw streams and timer."""
    command = [str(item) for item in command]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter_ns()
    process = subprocess.run(command, cwd=ROOT, env=environment(), capture_output=True, timeout=timeout)
    elapsed = time.perf_counter_ns() - start
    (destination / "stdout").write_bytes(process.stdout)
    (destination / "stderr").write_bytes(process.stderr)
    receipt = {"command": command, "cwd": str(ROOT), "exitCode": process.returncode,
               "elapsedNs": elapsed, "stdoutSha256": sha(destination / "stdout"),
               "stderrSha256": sha(destination / "stderr"), **binding}
    write_json(destination / "call.json", receipt)
    require(process.returncode == 0, "subprocess failed: " + str(destination / "stderr"))
    return receipt


def call_receipt(directory, expected_command, binding):
    directory = Path(directory)
    require(set(files_under(directory)) == {"stdout", "stderr", "call.json"}, "raw command closure differs")
    receipt = read_json(directory / "call.json")
    expected_keys = {"command", "cwd", "exitCode", "elapsedNs", "stdoutSha256", "stderrSha256", *binding}
    require(set(receipt) == expected_keys and receipt["command"] == [str(x) for x in expected_command]
            and receipt["cwd"] == str(ROOT) and type(receipt["exitCode"]) is int and receipt["exitCode"] == 0,
            "raw command/status differs")
    require(type(receipt["elapsedNs"]) is int and 0 < receipt["elapsedNs"] < 120_000_000_000,
            "invalid raw elapsed time")
    require(receipt["stdoutSha256"] == sha(directory / "stdout")
            and receipt["stderrSha256"] == sha(directory / "stderr")
            and all(receipt[key] == value for key, value in binding.items()), "raw command/cohort binding differs")
    return receipt


def codec_command(binary, output):
    return [str(binary), "--validate-address-wrap", str(output / "address-wrap-assessment.json"),
            str(output / "address-wrap-assessment.txt"), str(output / "address-wrap-assessment.dot")]


def codec_binding(output, identity):
    return {**identity, "assessmentSha256": sha(output / "address-wrap-assessment.json"),
            "outputHashes": {name: sha(output / name) for name in sorted(OUTPUT_NAMES)}}


def codec_result(output, assessment):
    return {"schema": "ariadne.i5c-codec-result/v1",
            "assessment_sha256": sha(output / "address-wrap-assessment.json"),
            "text_sha256": sha(output / "address-wrap-assessment.txt"),
            "json_sha256": sha(output / "address-wrap-assessment.json"),
            "dot_sha256": sha(output / "address-wrap-assessment.dot"),
            "scope_id": assessment["scope_id"], "content_id": assessment["content_id"],
            "evidence": len(assessment["evidence"]), "claims": len(assessment["claims"]),
            "conclusion": assessment["conclusion"]}


def authenticate_codec(binary, output, directory, identity, assessment, *, fresh):
    command = codec_command(binary, output)
    call_receipt(directory, command, codec_binding(output, identity))
    expected = codec_result(output, assessment)
    require(read_json(directory / "stdout") == expected, "retained codec result differs from exact assessment")
    if fresh:
        # The selected, hash-bound executable must actually decode/recompute this
        # report now. A JSON boolean, stored receipt or Python hash is no substitute.
        process = subprocess.run(command, cwd=ROOT, env=environment(), capture_output=True, timeout=120)
        require(process.returncode == 0 and strict_json(process.stdout.decode()) == expected,
                "fresh production strict codec authentication failed")


def validate_assessment(value, report, case):
    expected = case["oracle"]
    require(value.get("schema") == ASSESSMENT_SCHEMA and value.get("profile") == PROFILE,
            "wrong I5c assessment schema/profile")
    require(all(value["identity"][key] == report["identity"][key]
                for key in ("artifact_sha256", "snapshot_id", "query_id"))
            and value["identity"]["artifact_sha256"] == case["artifactSha256"]
            and value["question"] == {"site": case["site"], "memory_access": 0}, "assessment/raw/query identity differs")
    require(value["limits"] == {"max_evidence": 64, "max_claims": 64}
            and all(type(v) is int for v in value["limits"].values()), "nondefault I5c limits")
    require(value["conclusion"] == expected["conclusion"] and value["truncated"] is expected["truncated"]
            and value["inputs_complete"] is expected["inputs_complete"], "assessment differs from independent oracle")
    arithmetic = expected["arithmetic"]
    if arithmetic is None:
        require(value["arithmetic"] is None, "unsupported arithmetic survived")
    else:
        wanted = {key: item for key, item in arithmetic.items() if key != "quotient"}
        for key in ("base_value", "displacement_bits", "effective_address"):
            wanted[key] = {"value": wanted[key]}
        require(value["arithmetic"] == wanted, "wide arithmetic differs from independent raw oracle")
    for key in ("input_evidence_count",):
        if key in expected:
            require(type(value[key]) is int and value[key] == expected[key], "oracle count differs: " + key)
    for key, field in (("retained_evidence_count", "evidence"), ("retained_claims", "claims")):
        if key in expected:
            require(len(value[field]) == expected[key], "oracle retained count differs: " + key)
    require(set(expected.get("required_gaps", [])) <= set(value["gaps"]), "mandatory raw-oracle gap absent")
    instructions = [e["data"]["instruction"] for e in value["evidence"] if e["data"]["kind"] == "instruction"]
    require(len(instructions) == 1, "selected captured instruction absent/duplicated")
    raw = case["rawObservation"]
    code = raw["code"] if "code" in raw else raw["instruction"]["bytes"]
    require(instructions[0]["bytes_hex"] == code and instructions[0]["captured"] is True,
            "assessment selected bytes differ from captured oracle")


def validate_presentations(output, value):
    """Independent narrow checks complement exact Rust re-render authentication."""
    text = (output / "address-wrap-assessment.txt").read_text()
    lines = text.splitlines()
    requirements = ["requires: " + item for item in value["evidence_requirements"]]
    require([line for line in lines if line.startswith("requires:")] == requirements,
            "text dropped/reordered evidence requirements")
    require([line for line in lines if line.startswith("gap:")] == ["gap: " + gap for gap in value["gaps"]],
            "text dropped/reordered gaps")
    conclusion = {"consistent_with_evidence": "ConsistentWithEvidence",
                  "refuted_under_premises": "RefutedUnderPremises", "unknown": "Unknown"}[value["conclusion"]]
    require(lines[1] == "conclusion: " + conclusion, "text conclusion differs")
    if value["arithmetic"] is not None:
        at = lines.index("conditional arithmetic under the declared premises:")
        require(all(lines.index(line) < at for line in ["conclusion: " + conclusion,
                    *["gap: " + gap for gap in value["gaps"]], *requirements]), "text arithmetic precedes its limitations")
    dot = (output / "address-wrap-assessment.dot").read_text()
    first = dot.splitlines()[0]
    prefix = "// address_wrap_assessment: "
    require(first.startswith(prefix) and strict_json(first[len(prefix):]) == value,
            "DOT embedded assessment differs")


def cli_command(executables, case, output):
    # Backend remains the normal native default: no --analysis-backend override.
    return [executables["cli"], case["dump"], "--decoder-reference", executables["decoder"],
            "--entry", case["entry"], "--assess-address-wrap", case["site"],
            "--memory-access", "0", "--output-dir", str(output)]


def phase_command(executables, case):
    return [executables["benchmark"], case["dump"], executables["decoder"], case["entry"], case["site"], "6"]


def validate_case(directory, case, executables, identity, manifest, *, fresh):
    directory = Path(directory)
    require(read_json(directory / "oracle.json") == case, "retained independent case/raw inspection differs")
    hashes = None
    cli_times = []
    selected = None
    for number in range(6):
        run_root = directory / ("run-" + str(number))
        output = run_root / "output"
        closure = files_under(output)
        require(set(closure) == OUTPUT_NAMES, "CLI output inventory differs")
        current = {name: item["sha256"] for name, item in closure.items()}
        if hashes is not None:
            require(hashes == current, "CLI outputs changed between repetitions")
        hashes = current
        receipt = call_receipt(run_root / "cli", cli_command(executables, case, output), identity)
        report = read_json(output / "report.json")
        validate_backend_receipt(report, manifest)
        require(report["identity"]["artifact_sha256"] == case["artifactSha256"]
                and report["query"]["entries"] == [case["entry"]]
                and report["query"]["seeds"] == [case["site"]], "normal CLI raw/query differs")
        value = read_json(output / "address-wrap-assessment.json")
        validate_assessment(value, report, case)
        validate_presentations(output, value)
        authenticate_codec(executables["benchmark"], output, run_root / "codec", identity, value, fresh=fresh)
        if number:
            cli_times.append(receipt["elapsedNs"] / 1e6)
        selected = report, value, output
    report, value, output = selected
    call_receipt(directory / "phases", phase_command(executables, case), identity)
    csv_text = (directory / "phases/stdout").read_text()
    reader = csv.DictReader(io.StringIO(csv_text))
    require(reader.fieldnames == PHASE_FIELDS, "phase CSV field inventory differs")
    phase_rows = list(reader)
    require(all(set(row) == set(PHASE_FIELDS) for row in phase_rows), "malformed phase CSV row")
    phase_hash = hashlib.sha256(b"".join((output / ("address-wrap-assessment." + fmt)).read_bytes()
                                        for fmt in FORMATS)).hexdigest()
    enum = {"consistent_with_evidence": "ConsistentWithEvidence", "refuted_under_premises": "RefutedUnderPremises",
            "unknown": "Unknown"}[case["oracle"]["conclusion"]]
    times = validate_phase_rows(phase_rows, report, manifest,
                               {"warmups": 1, "repeats": 5, "phaseMedianBudgetMs": 10, "cliMedianBudgetMs": 1500},
                               conclusion=enum, output_sha256=phase_hash)
    for row in phase_rows:
        require(row["max_evidence"] == row["max_claims"] == "64"
                and row["scope_id"] == value["scope_id"] and row["content_id"] == value["content_id"]
                and row["evidence"] == str(len(value["evidence"])) and row["claims"] == str(len(value["claims"])),
                "phase count/default limit/content identity differs")
        require(all(int(row[key]) > 0 for key in ("binding_ns", "assessment_ns", "render_ns")), "zero phase duration")
    cli_median, phase_median = statistics.median(cli_times), statistics.median(times)
    return {"case": case["case"], "cliMedianMs": cli_median, "phaseMedianMs": phase_median,
            "cliSamplesMs": cli_times, "phaseSamplesMs": times,
            "cliSpreadMs": max(cli_times) - min(cli_times), "phaseSpreadMs": max(times) - min(times),
            "met": cli_median <= 1500 and phase_median <= 10}


def validate_record(path, *, fresh=True):
    path = Path(path).resolve()
    work = path.parent
    record = read_json(path)
    require(record.get("schema") == SCHEMA, "wrong measurement schema")
    require(record["contractSha256"] == sha(PERFORMANCE), "frozen contract digest differs")
    sources = source_inventory()
    require(record["sourceHashes"] == sources, "measurement source cohort is stale/incomplete")
    executables = {key: Path(value) for key, value in record["executables"].items()}
    require(set(executables) == {"cli", "benchmark", "decoder"}, "executable selection differs")
    tools = tool_inventory(executables)
    require(record["tools"] == tools, "measurement tool cohort is stale/incomplete")
    dependency = active_identity()
    require(dependency is not None and record["qualificationEnvironment"] == dependency, "sealed dependency identity differs")
    identity = cohort(sources, tools, dependency)
    require(record["cohort"] == identity, "measurement cohort receipt differs")
    cases = raw_cases(record["controlledConfiguration"])
    expected_names = contract()["fixtureCases"] + (contract()["controlledCases"] if record["controlledConfiguration"] else [])
    require(record["caseNames"] == expected_names and [row["case"] for row in cases] == expected_names,
            "timing workload inventory/order differs")
    require(files_under(work / "raw") == record["rawFiles"], "raw evidence file closure/hash/size differs")
    manifest = native_manifest()
    require(record["nativeManifest"] == manifest, "native helper build manifest differs")
    summaries = [validate_case(work / "raw" / case["case"], case, executables, identity, manifest, fresh=fresh)
                 for case in cases]
    fixture = all(row["met"] for row in summaries[:10])
    controlled = summaries[10:]
    partial = len(controlled) == 8 and all(row["met"] for row in controlled if row["case"].endswith("-partial"))
    full = len(controlled) == 8 and all(row["met"] for row in controlled if row["case"].endswith("-full"))
    result = {"fixtureTimingPassed": fixture, "controlledWindowsPartialTimingPassed": partial,
              "controlledWindowsFullTimingPassed": full,
              "passed": fixture and (not record["controlledConfiguration"] or partial and full), "summaries": summaries}
    require(record["result"] == result, "claimed medians/timing flags differ from raw recomputation")
    require(sources == source_inventory() and tools == tool_inventory(executables)
            and dependency == active_identity(), "cohort changed during validation")
    return result


def collect(args):
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    executables = {"cli": args.cli.resolve(), "benchmark": args.benchmark.resolve(), "decoder": args.decoder.resolve()}
    configuration = None
    if args.captures is not None:
        require(args.build is not None and args.expected_build_sha256 is not None,
                "owned captures require --build and independent --expected-build-sha256")
        require(re.fullmatch(r"[0-9a-f]{64}", args.expected_build_sha256), "invalid expected build digest")
        configuration = {"captures": str(args.captures.resolve()), "build": str(args.build.resolve()),
                         "expectedBuildSha256": args.expected_build_sha256}
    else:
        require(args.build is None and args.expected_build_sha256 is None, "build arguments require --captures")
    dependency = active_identity()
    require(dependency is not None, "run through the sealed dependency snapshot")
    before, tools = source_inventory(), tool_inventory(executables)
    identity = cohort(before, tools, dependency)
    manifest = native_manifest()
    cases = raw_cases(configuration)
    summaries = []
    for case in cases:
        destination = work / "raw" / case["case"]
        destination.mkdir(parents=True)
        write_json(destination / "oracle.json", case)
        for number in range(6):
            run_root = destination / ("run-" + str(number))
            run_root.mkdir()
            output = run_root / "output"
            run(cli_command(executables, case, output), run_root / "cli", binding=identity)
            run(codec_command(executables["benchmark"], output), run_root / "codec",
                binding=codec_binding(output, identity))
        run(phase_command(executables, case), destination / "phases", binding=identity)
        summary = validate_case(destination, case, executables, identity, manifest, fresh=True)
        summaries.append(summary)
        print(case["case"], "CLI", round(summary["cliMedianMs"], 3), "ms; phases",
              round(summary["phaseMedianMs"], 3), "ms;", "PASS" if summary["met"] else "OVER BUDGET", flush=True)
    require(before == source_inventory() and tools == tool_inventory(executables)
            and dependency == active_identity(), "source/tool/dependency changed during measurement")
    fixture = all(row["met"] for row in summaries[:10])
    partial = configuration is not None and all(row["met"] for row in summaries[10:] if row["case"].endswith("-partial"))
    full = configuration is not None and all(row["met"] for row in summaries[10:] if row["case"].endswith("-full"))
    result = {"fixtureTimingPassed": fixture, "controlledWindowsPartialTimingPassed": partial,
              "controlledWindowsFullTimingPassed": full, "passed": fixture and (configuration is None or partial and full),
              "summaries": summaries}
    record = {"schema": SCHEMA, "recordedUtc": datetime.now(timezone.utc).isoformat(),
              "contractSha256": sha(PERFORMANCE), "sourceHashes": before, "tools": tools,
              "qualificationEnvironment": dependency, "cohort": identity,
              "executables": {key: str(path) for key, path in executables.items()},
              "nativeManifest": manifest, "controlledConfiguration": configuration,
              "caseNames": [case["case"] for case in cases], "rawFiles": files_under(work / "raw"), "result": result,
              "scope": "Each frozen workload separately; native completed-analysis phases and native-default release CLI. "
                       "Codec authentication is not raw-capture authentication. No I4, full I5c, packaged-release, history or root-cause credit."}
    path = work / "report.json"
    write_json(path, record)
    validate_record(path)
    print("Report:", path, flush=True)
    return result["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--output", type=Path)
    selection.add_argument("--validate", type=Path, help="fresh strict codec/raw/cohort validation of retained report")
    parser.add_argument("--captures", type=Path)
    parser.add_argument("--build", type=Path)
    parser.add_argument("--expected-build-sha256")
    parser.add_argument("--cli", type=Path, default=ROOT / "target/release/ariadne-minidump")
    parser.add_argument("--benchmark", type=Path, default=ROOT / "target/release/i5c")
    parser.add_argument("--decoder", type=Path, default=ROOT / "target/ariadne-llvm-mc")
    args = parser.parse_args()
    try:
        if args.validate:
            require(args.captures is None and args.build is None and args.expected_build_sha256 is None,
                    "--validate uses the retained, rechecked capture selection")
            result = validate_record(args.validate)
            print(json.dumps({"reportSha256": sha(args.validate), **result}, indent=2), flush=True)
            passed = result["passed"]
        else:
            passed = collect(args)
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        print("I5c performance gate failed:", error, file=sys.stderr, flush=True)
        return 1
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
