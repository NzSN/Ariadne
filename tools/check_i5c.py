#!/usr/bin/env python3
"""Coordinate fresh W4/W5 qualification without crediting unavailable prerequisites.

Run --preflight-only before scheduling remote work. Full campaigns need the
eight I5c captures, retained legacy bytes, earlier I5a/I5b capture sets, I4
profile baseline and retained W2/W3 runtime logs. No missing tier is waived.
"""
import argparse
import hashlib
from pathlib import Path
import tarfile

from i5c_qualification import (FIXTURES, ROOT, artifact, command, named_rows,
                               prerequisite_report, read_json, require, sha,
                               retained_path, sources, write_json)


def verify_archive(path, entries):
    """Stream every member; reject duplicates, links, missing and extra entries."""
    seen = set()
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            require(member.isfile() and member.name not in seen and member.name in entries,
                    "unexpected/non-file/duplicate archive member: " + member.name)
            seen.add(member.name)
            digest = hashlib.sha256()
            size = 0
            with archive.extractfile(member) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    size += len(block)
                    digest.update(block)
            require(entries[member.name] == {"bytes": size, "sha256": digest.hexdigest()},
                    "archive member size/hash differs: " + member.name)
    require(seen == set(entries), "archive member closure differs")


def runtime_files(index_path, expected_digest):
    require(sha(index_path) == expected_digest, "retained runtime export index digest differs")
    index = read_json(index_path)
    require(index.get("schema") == "ariadne.i5c-w2-w3-runtime-export/v1"
            and set(index.get("stages", {})) == {"W2", "W3"}, "both retained runtime stages are required")
    result = {"retained-runtime/export-index.json": Path(index_path)}
    for stage, relative in (("W2", "20261020/w2"), ("W3", "20261021/w3")):
        row = index["stages"][stage]
        root = Path(row["root"]).resolve()
        require(root.is_dir() and row.get("files"), "missing retained runtime export: " + stage)
        qualified = ROOT / "evidence/Ariadne/address-wrap" / relative / "qualification.json"
        payload = retained_path(qualified)
        expected_qualification = artifact(payload)["sha256"]
        require(row.get("qualificationSha256") == expected_qualification, "retained stage identity differs")
        original = read_json(payload)
        require(original.get("passed") is True and original.get("records"), "retained stage did not qualify")
        paths = {str(p.relative_to(root)): p for p in root.rglob("*") if p.is_file()}
        require(set(paths) == set(row["files"]) and "qualification.json" in paths,
                "retained runtime pathname closure differs")
        require(sha(paths["qualification.json"]) == expected_qualification, "retained original qualification differs")
        for metadata in qualified.parent.iterdir():
            if metadata.is_file():
                require(metadata.name in paths and sha(paths[metadata.name]) == sha(retained_path(metadata)),
                        "published stage inputs/metadata omitted or changed: " + stage + "/" + metadata.name)
        # The export cannot redefine which runtime streams the old campaigns
        # produced. Require every verbatim stream bound by the original receipt,
        # preserving its absolute campaign path below this export root.
        for receipt in original["records"]:
            require(receipt.get("passed") is True and receipt.get("exit") == 0
                    and receipt.get("timed_out") is False, "retained command lacks a successful receipt")
            for stream in ("stdout", "stderr"):
                expected = receipt[stream]
                name = expected["path"].lstrip("/")
                require(name in row["files"] and row["files"][name] == {
                    "bytes": expected["bytes"], "sha256": expected["sha256"]},
                    "missing/changed originally bound runtime stream: " + stage + "/" + name)
            cases = receipt.get("case_records")
            if cases:
                name = cases["path"].lstrip("/")
                published = qualified.parent / Path(name).name
                require(name in row["files"] and row["files"][name]["sha256"] == artifact(retained_path(published))["sha256"],
                        "retained named-case records differ from the publication")
        for name, path in paths.items():
            require(not path.is_symlink() and not any(p.is_symlink() for p in path.parents if p != root.parent),
                    "symlink in retained runtime export")
            item = artifact(path)
            require(row["files"][name] == {"bytes": item["bytes"], "sha256": item["sha256"]},
                    "retained runtime bytes differ: " + stage + "/" + name)
            result["retained-runtime/" + stage + "/" + name] = path
    return result


def seal(work, before, inputs, publication):
    archive_path = publication / "evidence.tar.gz"
    files = {"sources/" + name: ROOT / name for name in before}
    files.update(inputs)
    for path in work.rglob("*"):
        relative = path.relative_to(work)
        if path.is_file() and not {"sut", ".seal-pending", "sealed"}.intersection(relative.parts):
            files["qualification/" + str(relative)] = path
    files["qualification/report.json"] = publication / "report.json"
    entries = {}
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, path in sorted(files.items()):
            require(not path.is_symlink(), "cannot seal a symlink: " + str(path))
            item = artifact(path)
            entries[name] = {"bytes": item["bytes"], "sha256": item["sha256"]}
            archive.add(path, arcname=name, recursive=False)
    verify_archive(archive_path, entries)
    return {"schema": "ariadne.i5c-evidence/v1", "verified": True,
            "archiveSha256": sha(archive_path), "entries": entries,
            "qualificationReportSha256": sha(publication / "report.json")}


def publish_acceptance(work, record, before, inputs):
    """Publish positive flags only with a completely verified sealed directory."""
    pending = {**record, "passed": False, "sourceFixtureAcceptance": False,
               "controlledWindowsPartialAcceptance": False, "controlledWindowsFullAcceptance": False,
               "fullI5cAcceptance": False, "failure": record["failure"] or "evidence sealing pending"}
    write_json(work / "report.json", pending)
    if not record["passed"]:
        return False
    try:
        publication = work / ".seal-pending"
        publication.mkdir()
        write_json(publication / "report.json", record)
        manifest = seal(work, before, inputs, publication)
        write_json(publication / "evidence-manifest.json", manifest)
        require(sources() == before, "sources changed while sealing evidence")
        publication.rename(work / "sealed")
        write_json(work / "report.json", record)
        return True
    except (OSError, ValueError, tarfile.TarError) as error:
        pending["failure"] = "evidence sealing failed: " + str(error)
        write_json(work / "report.json", pending)
        return False


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    for name in ("captures", "build", "legacy-baseline", "i5a-captures", "i5b-captures", "i4-profiles-root", "runtime-index"):
        parser.add_argument("--" + name, type=Path)
    for name in ("expected-build-sha256", "expected-legacy-baseline-sha256", "expected-runtime-index-sha256"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    work = args.output.resolve()
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
        for name in ("captures", "build", "legacy_baseline", "i5a_captures", "i5b_captures", "i4_profiles_root", "runtime_index",
                     "expected_build_sha256", "expected_legacy_baseline_sha256", "expected_runtime_index_sha256"):
            require(getattr(args, name) is not None, "full qualification requires --" + name.replace("_", "-"))
        inputs.update(runtime_files(args.runtime_index, args.expected_runtime_index_sha256))
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
        inputs.update(runtime_files(args.runtime_index, args.expected_runtime_index_sha256))
        dependency = preflight["qualificationEnvironment"]
        inputs["dependencies/mirrorrust-snapshot.json"] = Path(dependency["manifestPath"])
        for name, item in preflight["tools"].items():
            inputs["tools/" + name + "/" + Path(item["path"]).name] = Path(item["path"])
        for name in ("ariadne-minidump", "i5c", "i5a", "i5b", "i4_profile"):
            inputs["tools/release/" + name] = ROOT / "target/release" / name
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
