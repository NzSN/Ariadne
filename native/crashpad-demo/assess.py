#!/usr/bin/env python3
"""Qualify native I5a analysis of preserved, independently checked Windows captures."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from i5a_native_contract import (  # noqa: E402
    environment, native_manifest, source_inventory, strict_json, tool_hashes,
    validate_backend_receipt, validate_phase_rows, validate_source_fixture_record,
)
from with_mirrorrust_snapshot import active_identity  # noqa: E402

CRITERIA = {"warmups": 1, "repeats": 5, "phaseMedianBudgetMs": 10, "cliMedianBudgetMs": 1500}
CORE_REPORTS = ("report.txt", "report.json", "report.dot")
ASSESSMENT_REPORTS = tuple("zero-address-assessment." + suffix for suffix in ("txt", "json", "dot"))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return strict_json(Path(path).read_text())


def validate_performance_contract(contract):
    require(contract.get("schema") == "ariadne.i5a-performance-contract/v1"
            and contract.get("profile") == "release", "wrong performance contract")
    require(all(type(contract.get(key)) is int and contract[key] == value
                for key, value in CRITERIA.items()), "frozen performance criteria changed")


def validate_capture_provenance(captures, mode, inspection_path, inspector_sha):
    """Check current raw inspection separately from the historical producer records."""
    case = captures / mode
    build_path = captures / "build/build.json"
    inputs_path = captures / "build/build-inputs.json"
    capture_path = case / "capture.json"
    historical_path = case / "inspection.json"
    inspection = read_json(inspection_path)
    historical = read_json(historical_path)
    capture = read_json(capture_path)
    build = read_json(build_path)
    inputs = read_json(inputs_path)
    require(mode in ("partial", "full"), "unsupported capture mode")
    require(inspection.get("schema") == "ariadne.crashpad-demo-capture-inspection/v1"
            and inspection.get("passed") is True
            and inspection.get("requested_dump_mode") == mode, "invalid current inspection")
    require(historical.get("schema") == "ariadne.crashpad-demo-capture-inspection/v1"
            and historical.get("passed") is True
            and historical.get("requested_dump_mode") == mode, "invalid historical inspection")
    require(inspection.get("local_source_files", {}).get("inspect_capture.py", {}).get("sha256")
            == inspector_sha, "current inspection tool changed or is missing")
    # Fresh local crash_demo.cc hashes describe nearby files, not producer sources.
    require(capture.get("schema") == "ariadne.crashpad-demo-capture/v1"
            and capture.get("captureCreated") is True
            and capture.get("uploadsEnabled") is False
            and capture.get("host") == "native Windows"
            and capture.get("mode") == mode, "invalid capture record")
    require(build.get("schema") == "ariadne.crashpad-demo-windows-build/v1"
            and build.get("passed") is True and build.get("sourcesStable") is True
            and build.get("architecture") == "x64", "invalid historical build")
    require(capture.get("buildRecordSha256") == sha(build_path), "capture/build record changed")
    require(inputs.get("schema") == "ariadne.crashpad-demo-build-inputs/v1"
            and build.get("inputs", {}).get("inputsSha256") == sha(inputs_path),
            "historical build inputs changed")
    revision = build.get("crashpadRevision")
    require(isinstance(revision, str) and len(revision) == 40
            and capture.get("crashpadRevision") == inputs.get("crashpadRevision") == revision,
            "capture/build revision mismatch")
    binaries = build.get("binaryHashes", {})
    require(capture.get("handlerSha256") == binaries.get("crashpad_handler.exe")
            and isinstance(capture.get("handlerSha256"), str)
            and len(capture["handlerSha256"]) == 64, "capture/build handler mismatch")
    tracked = [build_path, inputs_path, capture_path, historical_path, inspection_path]
    input_hashes = {}
    for key, filename in (("dump", "capture.dmp"), ("witness", "witness.json"),
                          ("executable", "ariadne_crash_demo.exe")):
        path = case / filename
        digest = sha(path)
        for observed in (inspection, historical):
            identity = observed.get("inputs", {}).get(key, {})
            require(identity.get("sha256") == digest and identity.get("size_bytes") == path.stat().st_size,
                    f"inspection input changed: {mode}/{filename}")
        recorded = (capture.get("dump", {}).get("sha256") if key == "dump"
                    else capture.get(key + "Sha256"))
        require(recorded == digest, f"capture input changed: {mode}/{filename}")
        if key == "dump":
            require(capture["dump"].get("bytes") == path.stat().st_size, "capture dump size changed")
        if key == "executable":
            require(binaries.get(filename) == digest, "capture/build executable mismatch")
        input_hashes[key] = digest
        tracked.append(path)
    witness = read_json(case / "witness.json")
    require(capture.get("processId") == inspection.get("process_id") == witness.get("process_id"),
            "capture/inspection/witness process mismatch")
    require(witness.get("dump_mode") == mode, "witness mode mismatch")
    query = inspection.get("query", {})
    require(query == historical.get("query")
            and query.get("entry_points") == [witness.get("fault_function_entry")]
            and query.get("slice_seeds") == [query.get("fault_instruction")]
            and query.get("memory_access_index") == 0, "inspection query changed")
    producer_sources = inputs.get("demoSourceHashes", {})
    require(set(producer_sources) == {"BUILD.gn", "crash_demo.cc", "fault.cc"},
            "incomplete historical producer source inventory")
    for name, digest in producer_sources.items():
        require(inputs.get("sourceHashes", {}).get("examples/ariadne_demo/" + name) == digest,
                "historical producer source bindings disagree")
        if name != "BUILD.gn":
            require(historical.get("local_source_files", {}).get(name, {}).get("sha256") == digest,
                    "historical inspection/producer source mismatch")
    provenance = {
        "buildRecordSha256": sha(build_path), "buildInputsSha256": sha(inputs_path),
        "captureRecordSha256": sha(capture_path), "inspectionSha256": sha(inspection_path),
        "historicalInspectionSha256": sha(historical_path), "inputHashes": input_hashes,
        "crashpadRevision": revision, "handlerSha256": capture["handlerSha256"],
        "historicalProducerSourceHashes": producer_sources,
        "inspectionToolSha256": inspector_sha,
        "inspectionLocalSourceObservations": inspection["local_source_files"],
        "producerScope": "Preserved historical build/capture records bind producer identities; current inspection source observations do not establish original executable provenance.",
    }
    return inspection, provenance, {str(path): sha(path) for path in tracked}


def validate_cli_report(report, inspection, manifest):
    receipt = validate_backend_receipt(report, manifest)
    query = inspection["query"]
    canonical = lambda values: [f"0x{int(value, 16):016x}" for value in values]
    require(report.get("schema") == "ariadne-minidump-report-v1"
            and report.get("identity", {}).get("artifact_sha256") == inspection["inputs"]["dump"]["sha256"]
            and report.get("identity", {}).get("platform") == "windows"
            and report.get("query", {}).get("entries") == canonical(query["entry_points"])
            and report.get("query", {}).get("seeds") == canonical(query["slice_seeds"])
            and report.get("query", {}).get("exception_rip_seed") is False,
            "wrong artifact, platform or query")
    return receipt


def validate_assessment(result, report, inspection):
    require(result.get("schema") == "ariadne.zero-address-assessment/v1"
            and result.get("profile") == "windows-amd64-av-scalar-mov-v1"
            and result.get("conclusion") == "consistent_with_evidence"
            and result.get("gaps") == [] and result.get("truncated") is False
            and result.get("evaluated_address", {}).get("value") == "0x0000000000000000"
            and all(result.get("identity", {}).get(key) == report["identity"][key]
                    for key in ("snapshot_id", "artifact_sha256", "query_id"))
            and result.get("question") == {
                "site": f"0x{int(inspection['query']['fault_instruction'], 16):016x}", "memory_access": 0},
            "assessment disagrees with independent null-write oracle")


def qualify_samples(phase_samples, cli_samples, contract):
    validate_performance_contract(contract)
    require(all(len(samples) == contract["repeats"]
                and all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                        for value in samples) for samples in (phase_samples, cli_samples)),
            "missing or invalid measured samples")
    phase_median, cli_median = statistics.median(phase_samples), statistics.median(cli_samples)
    return {"phaseMedianMs": phase_median, "assessmentCliMedianMs": cli_median,
            "phaseBudgetMet": phase_median <= contract["phaseMedianBudgetMs"],
            "cliBudgetMet": cli_median <= contract["cliMedianBudgetMs"],
            "passed": phase_median <= contract["phaseMedianBudgetMs"]
                      and cli_median <= contract["cliMedianBudgetMs"]}


def inspect_bundle(destination, operation, inspection, manifest):
    expected = CORE_REPORTS + (ASSESSMENT_REPORTS if operation == "assessment" else ())
    require({path.name for path in destination.iterdir()} == set(expected), "wrong report bundle inventory")
    hashes = {name: sha(destination / name) for name in expected}
    report = read_json(destination / "report.json")
    receipt = validate_cli_report(report, inspection, manifest)
    if operation == "assessment":
        validate_assessment(read_json(destination / "zero-address-assessment.json"), report, inspection)
    return hashes, report, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True,
                        help="preserved directory containing build/, partial/, and full/ records")
    parser.add_argument("--source-fixture-record", type=Path, required=True,
                        help="fresh passing ariadne.i5a-acceptance/v2 record")
    parser.add_argument("--inspection-dir", type=Path, required=True,
                        help="fresh partial/inspection.json and full/inspection.json records")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    captures, inspections, output = args.captures.resolve(), args.inspection_dir.resolve(), args.output.resolve()
    baseline_path = args.source_fixture_record.resolve()
    baseline = read_json(baseline_path)
    sources, tools_before, manifest = source_inventory(), tool_hashes(), native_manifest()
    validate_source_fixture_record(baseline, sources, tools_before,
                                   qualification_environment=active_identity())
    require(baseline.get("helperManifest") == manifest, "source/fixture native manifest changed")
    contract = read_json(ROOT / "tests/input/fixtures/i5a/performance.json")
    validate_performance_contract(contract)
    input_hashes = {str(baseline_path): sha(baseline_path)}
    prepared = {}
    for mode in ("partial", "full"):
        inspection_path = inspections / mode / "inspection.json"
        require(inspection_path != captures / mode / "inspection.json", "fresh inspection must preserve historical record")
        inspection, provenance, hashes = validate_capture_provenance(
            captures, mode, inspection_path, sha(Path(__file__).with_name("inspect_capture.py")))
        prepared[mode] = inspection, provenance
        input_hashes.update(hashes)
    output.mkdir(parents=True, exist_ok=False)
    cli, bench, decoder = (ROOT / name for name in (
        "target/release/ariadne-minidump", "target/release/i5a", "target/ariadne-llvm-mc"))
    env = environment()
    rows, phases, records = [], [], []
    for mode, (inspection, provenance) in prepared.items():
        case = captures / mode
        query = inspection["query"]
        entry, site = query["entry_points"][0], query["fault_instruction"]
        expected_core, measurements, equivalence = None, {}, {}
        assessment_report, assessment_destination = None, None
        for operation in ("base", "assessment"):
            samples, previous, receipts = [], None, []
            for number in range(contract["warmups"] + contract["repeats"]):
                destination = output / f"{mode}-{operation}-{number}"
                metrics = output / f"{mode}-{operation}-{number}.time"
                command = [str(cli), str(case / "capture.dmp"), "--decoder-reference", str(decoder),
                           "--entry", entry, "--seed", site, "--output-dir", str(destination)]
                if operation == "assessment":
                    command += ["--assess-zero-address", site, "--memory-access", "0"]
                start = time.perf_counter_ns()
                run = subprocess.run(["/usr/bin/time", "-f", "%e,%M", "-o", str(metrics), *command],
                                     env=env, capture_output=True, text=True, timeout=120)
                elapsed = (time.perf_counter_ns() - start) / 1e6
                require(run.returncode == 0, run.stderr)
                hashes, report, receipt = inspect_bundle(destination, operation, inspection, manifest)
                require(previous is None or previous == hashes, "nonrepeatable reports")
                previous = hashes
                receipts.append(receipt)
                core = {name: hashes[name] for name in CORE_REPORTS}
                require(expected_core is None or expected_core == core, "assessment changed the original reports")
                expected_core = core
                if operation == "assessment":
                    assessment_report, assessment_destination = report, destination
                warmup = number < contract["warmups"]
                rows.append({"capture": mode, "mode": operation, "run": number, "warmup": warmup,
                             "analysis_backend": "bap", "query_id": report["identity"]["query_id"],
                             "backend_query": receipt["query"], "elapsed_ms": elapsed,
                             "rss_kib": int(metrics.read_text().strip().split(",")[1])})
                if not warmup:
                    samples.append(elapsed)
            # Both sides of selection equivalence run outside the timed samples.
            verification_receipts = {}
            for selection in ("default", "explicit-bap"):
                destination = output / f"{mode}-{operation}-{selection}"
                verification_command = command.copy()
                verification_command[verification_command.index("--output-dir") + 1] = str(destination)
                if selection == "explicit-bap":
                    verification_command += ["--analysis-backend", "bap"]
                run = subprocess.run(verification_command, env=env, capture_output=True, text=True, timeout=120)
                require(run.returncode == 0, run.stderr)
                verification_hashes, _, verification_receipt = inspect_bundle(
                    destination, operation, inspection, manifest)
                require(previous == verification_hashes, "default/explicit native reports differ")
                verification_receipts[selection] = verification_receipt
            equivalence[operation] = {"allReportsEqual": True, "outputHashes": previous,
                                      "backendReceipts": verification_receipts}
            measurements[operation] = {"samplesMs": samples, "medianMs": statistics.median(samples),
                                       "minMs": min(samples), "maxMs": max(samples),
                                       "outputHashes": previous, "backendReceipts": receipts}
        run = subprocess.run([str(bench), str(case / "capture.dmp"), str(decoder), entry, site,
                              str(contract["warmups"] + contract["repeats"])],
                             env=env, capture_output=True, text=True, timeout=120, check=True)
        phase_rows = list(csv.DictReader(io.StringIO(run.stdout)))
        output_digest = hashlib.sha256(b"".join((assessment_destination / name).read_bytes()
                                               for name in ASSESSMENT_REPORTS)).hexdigest()
        phase_samples = validate_phase_rows(phase_rows, assessment_report, manifest, contract,
                                            conclusion="ConsistentWithEvidence", output_sha256=output_digest)
        phases.extend({"capture": mode, **row} for row in phase_rows)
        qualification = qualify_samples(phase_samples, measurements["assessment"]["samplesMs"], contract)
        records.append({"capture": mode, "dumpSha256": provenance["inputHashes"]["dump"],
                        **provenance, "query": query, "phaseSamplesMs": phase_samples,
                        **qualification, "measurements": measurements,
                        "defaultExplicitEquivalence": equivalence, "defaultNativeVerified": True})
        print(mode, "PASS" if qualification["passed"] else "OVER BUDGET",
              f"{qualification['phaseMedianMs']:.3f} ms phases;",
              f"{qualification['assessmentCliMedianMs']:.3f} ms CLI", flush=True)
    for name, values in (("cli.csv", rows), ("phase.csv", phases)):
        with (output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(values)
    stable = sources == source_inventory()
    tools_stable = tools_before == tool_hashes() and manifest == native_manifest()
    inputs_stable = all(Path(name).is_file() and sha(name) == digest for name, digest in input_hashes.items())
    passed = stable and tools_stable and inputs_stable and all(record["passed"] for record in records)
    record = {"schema": "ariadne.crashpad-demo-assessment/v2",
              "recordedUtc": datetime.now(timezone.utc).isoformat(), "passed": passed,
              "controlledWindowsCasePassed": passed, "originalWindowsI4AcceptancePassed": False,
              "profile": "release", "analysisBackend": "bap", "analysisProfile": "captured-fixed-input/v1",
              "defaultNativeVerified": True, "helperManifest": manifest,
              "sourceFixtureRecordSha256": input_hashes[str(baseline_path)], "sourceHashes": sources,
              "sourcesStable": stable, "tools": tools_before, "toolsStable": tools_stable,
              "inputHashes": input_hashes, "inputsStable": inputs_stable,
              "performanceCriteria": dict(CRITERIA), "records": records,
              "sampleHashes": {name: sha(output / name) for name in ("cli.csv", "phase.csv")},
              "scope": "One preserved controlled native Windows null-write demo, captured in partial/full mode, freshly inspected and assessed with the native BAP analysis default on the Linux host. No original Windows I4, root-cause inference, or general Windows workload claim."}
    record["qualificationEnvironment"] = active_identity()
    (output / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Report: {output / 'report.json'}", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
