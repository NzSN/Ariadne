#!/usr/bin/env python3
"""Coordinate fresh W4/W5 qualification without crediting unavailable prerequisites.

Run --preflight-only before scheduling remote work. Full campaigns need the
eight I5c captures, checked-in golden values, applicable I5a/I5b capture sets
and the I4 profile baseline. The current native matrix replaces old runtime exports.
"""
import argparse
import hashlib
from pathlib import Path
from run_output import run_output
import tarfile

from i5c_qualification import (FIXTURES, ROOT, artifact, command, named_rows,
                               prerequisite_report, read_json, require, sha,
                               sources, write_json)








def publish_acceptance(work, record, before, inputs):
    """Publish only a transient current-run result after checking live inputs."""
    pending = {**record, 'passed': False, 'sourceFixtureAcceptance': False,
               'controlledWindowsPartialAcceptance': False, 'controlledWindowsFullAcceptance': False,
               'fullI5cAcceptance': False}
    try:
        require(record['passed'] is True, 'required tests did not pass')
        for path in inputs.values():
            artifact(path)
        require(sources() == before, 'sources changed during tests')
    except (OSError, ValueError) as error:
        pending['failure'] = str(error)
        write_json(work / 'report.json', pending)
        return False
    write_json(work / 'report.json', record)
    return True


def gate_plan(work):
    return [
        ("fixture-bytes", ["python3", "tests/input/fixtures/make_i5c.py", "--check"]),
        ("model-inputs", ["python3", "tools/check_i5c_model_inputs.py", "--check"]),
        ("model-projection", ["python3", "tools/check_i5c_model_projection.py"]),
        ("oracle-controls", ["python3", "-m", "unittest", "discover", "-s", "tests/input", "-p", "test_i5c*.py"]),
        ("qualification-controls", ["python3", "-m", "unittest", "discover", "-s", "tools", "-p", "test_i5c*.py"]),
        ("format", ["cargo", "fmt", "--all", "--", "--check"]),
        ("default-tests", ["cargo", "test", "--offline", "--locked"]),
        ("core-tests", ["cargo", "test", "--offline", "--locked", "--no-default-features"]),
        ("clippy", ["cargo", "clippy", "--offline", "--locked", "--all-features", "--all-targets", "--", "-D", "warnings"]),
        ("layout", ["python3", "tools/check_rust_layout.py"]),
        ("documentation", ["python3", "tools/check_doc_links.py"]),
        ("question-model", ["bash", "Specs/check-address-wrap.sh", work / "question-model"]),
        ("matrix-native114", ["cargo", "test", "--offline", "--locked", "--release", "--lib", "w3_", "--", "--include-ignored", "--show-output", "--test-threads=1"]),
        ("strict-reports", ["cargo", "test", "--offline", "--locked", "--release", "--test", "reports_address_wrap"]),
        ("cli-controls", ["python3", "tools/check_i5c_cli.py", "--output", work / "cli"]),
        ("mutations", ["python3", "tools/check_i5c_mutations.py", "--output", work / "mutations"]),
    ]


def run_gate(work, name, argv):
    receipt, stdout, _ = command(work / "gates" / name, "command", argv, timeout=14400)
    require(receipt["exitCode"] == 0 and not receipt["timedOut"], "required gate failed: " + name)
    print(name + ": PASS", flush=True)
    return receipt, stdout


def matrix_rows(stdout):
    rows = read_json(FIXTURES / "manifest.json")["cases"]
    decisions = named_rows(stdout, "I5C_W3_DECISION ", [row["name"] for row in rows])
    native = named_rows(stdout, "I5C_W3_NATIVE_DECISION ",
                        [row["name"] for row in rows if row["harness"] == "synthetic-capture"])
    require(all(row.get("native_preparation") is True and row.get("native_completed_analysis") is True
                and row.get("tier") == "native-raw-capture" for row in native),
            "supplied preparation cannot receive native matrix credit")
    from i5a_native_contract import strict_json
    bindings = [strict_json(line[len("I5C_W3_BINDING "):]) for line in stdout.splitlines()
                if line.startswith("I5C_W3_BINDING ")]
    identities = [(row["baseline_name"], row["variant"], row["max_evidence"], row["max_claims"]) for row in bindings]
    require(len(identities) == len(set(identities)) == 44 and all(
        row["passed"] is True and row["assessor_invoked"] is False for row in bindings),
        "binding controls incomplete or reached budgets")
    return {"decisions": decisions, "native": native, "bindings": bindings}


def producer_files(build_path, expected_digest):
    """Retain the immutable Windows producer inputs needed for reinspection."""
    build_path = Path(build_path)
    require(sha(build_path) == expected_digest, "controlled producer build digest differs")
    build = read_json(build_path)
    directory = build_path.parent
    prepared_path = directory / "build-inputs.json"
    prepared = read_json(prepared_path)
    require(sha(prepared_path) == build["inputs"]["inputsSha256"]
            and sha(directory / "source.tar.gz") == build["inputs"]["sourceArchiveSha256"],
            "controlled producer inputs differ")
    import sys
    sys.path.insert(0, str(ROOT / "native/crashpad-demo"))
    from inspect_i5c import BINARY_NAMES, source_path
    files = {"producer/" + name: directory / name for name in
             ("build.json", "build-inputs.json", "source.tar.gz")}
    for name, digest in prepared["sourceHashes"].items():
        path = source_path(directory / "source", name)
        require(sha(path) == digest, "controlled producer source differs: " + name)
        files["producer/source/" + name.replace("\\", "/")] = path
    for name in ("gn.exe", "ninja.exe"):
        path = directory / "tools" / name
        require(sha(path) == build["toolHashes"][name], "controlled producer tool differs: " + name)
        files["producer/tools/" + name] = path
    require(set(build["binaryHashes"]) == BINARY_NAMES, "controlled producer binary closure differs")
    for name, digest in build["binaryHashes"].items():
        path = source_path(directory / "source", "out/Release/" + name)
        require(sha(path) == digest, "controlled producer binary differs: " + name)
        files["producer/source/out/Release/" + name] = path
    for name in ("tools.ensure", "owner.json", "tools.log", "gn.log", "gn-repeat.log", "build.log",
                 "arm64-rejection.log", "gn-version.log", "ninja-version.log", "clang-version.log"):
        path = directory / name
        require(path.is_file(), "controlled producer log missing: " + name)
        files["producer/" + name] = path
    return files


def inspect_i5a(work, captures):
    for mode in ("partial", "full"):
        destination = work / "i5a-inspection" / mode
        destination.mkdir(parents=True)
        case = captures / mode
        receipt, _ = run_gate(work, "i5a-inspect-" + mode, [
            "python3", "native/crashpad-demo/inspect_capture.py",
            "--dump", case / "capture.dmp", "--witness", case / "witness.json",
            "--executable", case / "ariadne_crash_demo.exe", "--output", destination / "inspection.json"])
        yield {"gate": "i5a-inspect-" + mode, **receipt}


def compiled_files(work):
    """Seal the actual selected observers, product binaries and mutant sources."""
    cli = read_json(work / "cli/report.json")
    mutations = read_json(work / "mutations/report.json")
    require(cli["passed"] is True and mutations["passed"] is True
            and len(mutations["mutants"]) == 24, "compiled evidence is incomplete")
    files = {}
    selected = [cli[key] for key in ("cli", "suite", "unit")]
    for row in mutations["mutants"]:
        selected.extend(row[kind]["executable"] for kind in ("positive", "negative"))
        sut = work / "mutations" / row["name"] / "sut"
        for name, change in row["changes"].items():
            path = sut / name
            require(sha(path) == change["after"], "mutant source changed before sealing")
            files["mutants/" + row["name"] + "/" + name] = path
        for name in ("Cargo.toml", "Cargo.lock"):
            files["mutants/" + row["name"] + "/" + name] = sut / name
    for item in selected:
        require(artifact(item["path"]) == item, "selected compiled observer changed before sealing")
        files["executables/" + item["sha256"] + "/" + Path(item["path"]).name] = Path(item["path"])
    # Integration-test compilation also builds the CLI selected by its embedded
    # CARGO_BIN_EXE. Retain that product, including the seed-to-root mutant.
    from i5a_native_contract import strict_json
    logs = [log for root in (work / "cli", work / "mutations") for log in root.rglob("build.stdout")]
    for log in logs:
        for line in log.read_text().splitlines():
            row = strict_json(line)
            if row.get("reason") == "compiler-artifact" and row.get("executable"):
                item = artifact(row["executable"])
                files["executables/" + item["sha256"] + "/" + Path(item["path"]).name] = Path(item["path"])
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    for name in ("captures", "build", "legacy-baseline", "i5a-captures", "i5b-captures", "i4-profiles-root"):
        parser.add_argument("--" + name, type=Path)
    for name in ("expected-build-sha256", "expected-legacy-baseline-sha256"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    work = run_output(args.output)
    work.mkdir(parents=True, exist_ok=False)
    before = sources()
    preflight = prerequisite_report()
    write_json(work / "prerequisites.json", preflight)
    if args.preflight_only:
        write_json(work / "report.json", {
            "schema": "ariadne.i5c-qualification/v1", "passed": False,
            "sourceFixtureAcceptance": False, "controlledWindowsPartialAcceptance": False,
            "controlledWindowsFullAcceptance": False, "fullI5cAcceptance": False,
            "prerequisitesPassed": preflight["passed"], "qualificationExecuted": False,
            "sourceHashes": before, "sourcesStable": sources() == before,
            "qualificationEnvironment": preflight["qualificationEnvironment"], "tools": preflight["tools"],
            "gates": [], "failure": None if preflight["passed"] else "qualification prerequisites unavailable"})
        print("Report:", work / "report.json", flush=True)
        return 0 if preflight["passed"] else 1
    gates, nested, inputs = [], {}, {}
    failure = None
    try:
        require(preflight["passed"], "qualification prerequisites unavailable; see prerequisites.json")
        for name in ("captures", "build", "legacy_baseline", "i5a_captures", "i5b_captures", "i4_profiles_root",
                     "expected_build_sha256", "expected_legacy_baseline_sha256"):
            require(getattr(args, name) is not None, "full qualification requires --" + name.replace("_", "-"))
        inputs.update(producer_files(args.build, args.expected_build_sha256))
        from compare_i5c_legacy import baseline
        legacy = baseline(args.legacy_baseline, args.expected_legacy_baseline_sha256)
        inputs["legacy/baseline.json"] = args.legacy_baseline
        # Adapt retained pre-W1 hashes for the older I5b runner, never observe
        # current CLI output to create its expected baseline.
        old = {key.removeprefix("i5a/"): value["sha256"] for key, value in legacy["outputs"].items() if key.startswith("i5a/")}
        legacy_i5a = work / "retained-i5a-baseline.json"
        write_json(legacy_i5a, {"schema": "ariadne.i5b-legacy-baseline/v1", "outputs": old,
                              "originBaselineSha256": args.expected_legacy_baseline_sha256})
        for name, argv in gate_plan(work):
            receipt, stdout = run_gate(work, name, argv)
            gates.append({"gate": name, **receipt})
            if name == "matrix-native114":
                nested[name] = matrix_rows(stdout)
            if name in ("cli-controls", "mutations"):
                path = work / ("cli" if name == "cli-controls" else name) / "report.json"
                record = read_json(path)
                require(record["passed"] is True and record["sourceHashes"] == before, "stale/incomplete " + name)
                nested[name] = artifact(path)
        following = [
            ("legacy-666", ["python3", "tools/compare_i5c_legacy.py", "--baseline", args.legacy_baseline,
                            "--expected-baseline-sha256", args.expected_legacy_baseline_sha256, "--output", work / "legacy"]),
            ("i5b-core-i5a-refresh", ["python3", "tools/check_i5b.py", "--output", work / "i5b", "--captures", args.i5b_captures,
                                     "--baseline", legacy_i5a]),
            ("i4-refresh", ["python3", "tools/check_i4_performance.py", "--regressions", work / "i5b/report.json",
                            "--profiles-root", args.i4_profiles_root, "--output", work / "i4"]),
        ]
        for name, argv in following:
            receipt, _ = run_gate(work, name, argv)
            gates.append({"gate": name, **receipt})
        regression = read_json(work / "i5b/report.json")
        require(regression["fullI5bAcceptance"] is True, "I5b controlled refresh is incomplete")
        source_i5a = work / "current-i5a-fixture-record.json"
        write_json(source_i5a, regression["records"]["i5a-regression"])
        gates.extend(inspect_i5a(work, args.i5a_captures))
        receipt, _ = run_gate(work, "i5a-controlled-refresh", ["python3", "native/crashpad-demo/assess.py",
            "--captures", args.i5a_captures, "--source-fixture-record", source_i5a,
            "--inspection-dir", work / "i5a-inspection", "--output", work / "i5a-controlled"])
        gates.append({"gate": "i5a-controlled-refresh", **receipt})
        require(read_json(work / "i5a-controlled/report.json")["controlledWindowsCasePassed"] is True,
                "I5a controlled refresh is incomplete")
        require(read_json(work / "i4/report.json")["fullI4RealCaptureAcceptance"] is True,
                "I4 refresh is incomplete")
        receipt, _ = run_gate(work, "release-products", ["cargo", "build", "--offline", "--locked", "--release",
            "--features", "bench", "--bin", "i5c"])
        gates.append({"gate": "release-products", **receipt})
        receipt, _ = run_gate(work, "normal-cli", ["cargo", "build", "--offline", "--locked", "--release", "--bin", "ariadne-minidump"])
        gates.append({"gate": "normal-cli", **receipt})
        receipt, _ = run_gate(work, "performance", ["python3", "tools/check_i5c_performance.py", "--output", work / "performance",
            "--captures", args.captures, "--build", args.build, "--expected-build-sha256", args.expected_build_sha256])
        gates.append({"gate": "performance", **receipt})
        from check_i5c_performance import controlled_cases, validate_record
        timing = validate_record(work / "performance/report.json")
        require(all(timing[key] is True for key in ("fixtureTimingPassed", "controlledWindowsPartialTimingPassed", "controlledWindowsFullTimingPassed")),
                "I5c timing tiers incomplete")
        nested["performance"] = timing
        # Independently re-inspect every owned capture immediately before sealing.
        controlled_cases({"captures": str(args.captures), "build": str(args.build), "expectedBuildSha256": args.expected_build_sha256})
        for label, directory in (("i5c", args.captures), ("i5a", args.i5a_captures), ("i5b", args.i5b_captures)):
            inputs.update({f"captures/{label}/{path.relative_to(directory)}": path for path in directory.rglob("*") if path.is_file()})
        dependency = preflight["qualificationEnvironment"]
        inputs["dependencies/mirrorrust-snapshot.json"] = Path(dependency["manifestPath"])
        for name, item in preflight["tools"].items():
            inputs["tools/" + name + "/" + Path(item["path"]).name] = Path(item["path"])
        for name in ("ariadne-minidump", "i5c", "i5a", "i5b", "i4_profile"):
            inputs["tools/release/" + name] = ROOT / "target/release" / name
        inputs.update(compiled_files(work))
        require(sources() == before, "source inventory changed during full campaign")
        require(prerequisite_report()["tools"] == preflight["tools"], "native tool inventory changed")
    except (OSError, ValueError, KeyError) as error:
        failure = str(error)
    passed = failure is None
    record = {"schema": "ariadne.i5c-qualification/v1", "passed": passed,
              "sourceFixtureAcceptance": passed, "controlledWindowsPartialAcceptance": passed,
              "controlledWindowsFullAcceptance": passed, "fullI5cAcceptance": passed,
              "sourceHashes": before, "sourcesStable": sources() == before,
              "qualificationEnvironment": preflight["qualificationEnvironment"], "tools": preflight["tools"],
              "gates": gates, "records": nested, "failure": failure,
              "scope": "Declared finite Windows AMD64 scalar MOV base/displacement wrap profile; no packaged release, history, root cause or universal refinement."}
    passed = publish_acceptance(work, record, before, inputs)
    print("Report:", work / "report.json", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
