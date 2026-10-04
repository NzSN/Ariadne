#!/usr/bin/env python3
"""Assess the two independently checked Windows captures with existing Ariadne."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True,
                        help="directory containing build/, partial/, and full/ records")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    captures = args.captures.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    baseline_path = ROOT / "evidence/Ariadne/i5a-validation.json"
    baseline = json.loads(baseline_path.read_text())
    if not baseline["sourceFixtureAcceptancePassed"] or not baseline["sourcesStable"]:
        raise RuntimeError("passing source/fixture qualification is required")
    sources = dict(baseline["sourceHashes"])
    for path in Path(__file__).parent.iterdir():
        if path.is_file() and path.suffix != ".md":
            sources[str(path.relative_to(ROOT))] = sha(path)
    for name, digest in sources.items():
        if sha(ROOT / name) != digest:
            raise RuntimeError(f"source differs from the qualification record: {name}")
    contract = json.loads((ROOT / "tests/input/fixtures/i5a/performance.json").read_text())
    cli = ROOT / "target/release/ariadne-minidump"
    bench = ROOT / "target/release/i5a"
    decoder = ROOT / "target/ariadne-llvm-mc"
    tool_paths = [cli, bench, decoder, ROOT / "target/ariadne-bap-lift",
                  ROOT / "tmp/bap-setup/stable/usr/local/lib/libbap.so.2.5.0"]
    tools_before = {str(path.relative_to(ROOT)): sha(path) for path in tool_paths}
    if tools_before != baseline["records"]["measurements"]["tools"]:
        raise RuntimeError("analysis tools differ from source/fixture-qualified binaries")
    environment = {**os.environ, "ARIADNE_BAP_HELPER": str(ROOT / "target/ariadne-bap-lift"),
                   "BAP_RUNTIME_ROOT": str(ROOT / "tmp/bap-setup/stable")}
    rows = []
    phases = []
    records = []
    for mode in ["partial", "full"]:
        case = captures / mode
        inspection = json.loads((case / "inspection.json").read_text())
        capture = json.loads((case / "capture.json").read_text())
        if not inspection["passed"] or not capture["captureCreated"] or capture["uploadsEnabled"]:
            raise RuntimeError(f"invalid capture/inspection: {mode}")
        for key, filename in [("dump", "capture.dmp"), ("witness", "witness.json"),
                              ("executable", "ariadne_crash_demo.exe")]:
            if sha(case / filename) != inspection["inputs"][key]["sha256"]:
                raise RuntimeError(f"inspection input changed: {mode}/{filename}")
        for name, identity in inspection["local_source_files"].items():
            if sha(Path(__file__).parent / name) != identity["sha256"]:
                raise RuntimeError(f"inspector source changed: {name}")
        query = inspection["query"]
        entry, site = query["entry_points"][0], query["fault_instruction"]
        expected_hashes = None
        measurements = {}
        for operation in ["base", "assessment"]:
            samples = []
            previous = None
            for number in range(contract["warmups"] + contract["repeats"]):
                destination = output / f"{mode}-{operation}-{number}"
                metrics = output / f"{mode}-{operation}-{number}.time"
                command = [str(cli), str(case / "capture.dmp"), "--decoder-reference", str(decoder),
                           "--entry", entry, "--seed", site, "--output-dir", str(destination)]
                if operation == "assessment":
                    command += ["--assess-zero-address", site, "--memory-access", "0"]
                start = time.perf_counter_ns()
                run = subprocess.run(["/usr/bin/time", "-f", "%e,%M", "-o", str(metrics), *command],
                                     env=environment, capture_output=True, text=True, timeout=120)
                elapsed = (time.perf_counter_ns() - start) / 1e6
                if run.returncode:
                    raise RuntimeError(run.stderr)
                hashes = {path.name: sha(path) for path in destination.iterdir() if path.is_file()}
                if previous is not None and previous != hashes:
                    raise RuntimeError("nonrepeatable reports")
                previous = hashes
                core = {name: hashes[name] for name in ["report.txt", "report.json", "report.dot"]}
                if expected_hashes is None:
                    expected_hashes = core
                elif expected_hashes != core:
                    raise RuntimeError("assessment changed the original reports")
                report = json.loads((destination / "report.json").read_text())
                if (report["identity"]["artifact_sha256"] != inspection["inputs"]["dump"]["sha256"]
                        or report["query"]["entries"] != [f"0x{int(entry, 16):016x}"]
                        or report["query"]["seeds"] != [f"0x{int(site, 16):016x}"]):
                    raise RuntimeError("wrong artifact or query")
                if operation == "assessment":
                    result = json.loads((destination / "zero-address-assessment.json").read_text())
                    if (result["conclusion"] != "consistent_with_evidence" or result["gaps"]
                            or result["evaluated_address"]["value"] != "0x0000000000000000"
                            or any(result["identity"][key] != report["identity"][key]
                                   for key in ["snapshot_id", "artifact_sha256", "query_id"])
                            or result["question"] != {"site": f"0x{int(site, 16):016x}", "memory_access": 0}):
                        raise RuntimeError("assessment disagrees with independent null-write oracle")
                warmup = number < contract["warmups"]
                rows.append({"capture": mode, "mode": operation, "run": number, "warmup": warmup,
                             "elapsed_ms": elapsed, "rss_kib": int(metrics.read_text().strip().split(",")[1])})
                if not warmup:
                    samples.append(elapsed)
            measurements[operation] = {"samplesMs": samples, "medianMs": statistics.median(samples),
                                       "minMs": min(samples), "maxMs": max(samples), "outputHashes": previous}
        run = subprocess.run([str(bench), str(case / "capture.dmp"), str(decoder), entry, site,
                              str(contract["warmups"] + contract["repeats"])],
                             env=environment, capture_output=True, text=True, timeout=120, check=True)
        phase_rows = list(csv.DictReader(io.StringIO(run.stdout)))
        if (len(phase_rows) != contract["warmups"] + contract["repeats"]
                or any(row["artifact_sha256"] != inspection["inputs"]["dump"]["sha256"]
                       or row["conclusion"] != "ConsistentWithEvidence" for row in phase_rows)
                or len({row["output_sha256"] for row in phase_rows}) != 1):
            raise RuntimeError("phase measurements are not repeatable and identity-bound")
        phases.extend({"capture": mode, **row} for row in phase_rows)
        phase_samples = [int(row["total_ns"]) / 1e6 for row in phase_rows[contract["warmups"]:]]
        phase_median = statistics.median(phase_samples)
        passed = (phase_median <= contract["phaseMedianBudgetMs"]
                  and measurements["assessment"]["medianMs"] <= contract["cliMedianBudgetMs"])
        records.append({"capture": mode, "dumpSha256": inspection["inputs"]["dump"]["sha256"],
                        "inspectionSha256": sha(case / "inspection.json"),
                        "captureRecordSha256": sha(case / "capture.json"), "query": query,
                        "phaseSamplesMs": phase_samples, "phaseMedianMs": phase_median,
                        "measurements": measurements, "passed": passed})
        print(mode, "PASS" if passed else "OVER BUDGET", f"{phase_median:.3f} ms phases;",
              f"{measurements['assessment']['medianMs']:.3f} ms CLI", flush=True)
    for name, values in [("cli.csv", rows), ("phase.csv", phases)]:
        with (output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(values)
    stable = all(sha(ROOT / name) == digest for name, digest in sources.items())
    tools_stable = all(sha(ROOT / name) == digest for name, digest in tools_before.items())
    passed = stable and tools_stable and all(record["passed"] for record in records)
    record = {"schema": "ariadne.crashpad-demo-assessment/v1",
              "recordedUtc": datetime.now(timezone.utc).isoformat(), "passed": passed,
              "controlledWindowsCasePassed": passed, "originalWindowsI4AcceptancePassed": False,
              "sourceFixtureRecordSha256": sha(baseline_path), "sourceHashes": sources,
              "sourcesStable": stable, "tools": tools_before, "toolsStable": tools_stable,
              "performanceCriteria": {key: contract[key] for key in
                                      ["warmups", "repeats", "phaseMedianBudgetMs", "cliMedianBudgetMs"]},
              "records": records,
              "sampleHashes": {name: sha(output / name) for name in ["cli.csv", "phase.csv"]},
              "scope": "One controlled native Windows null-write demo, captured in partial/full mode, assessed on the Linux host. No original Windows I4, root-cause inference, or general Windows workload claim."}
    (output / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Report: {output / 'report.json'}", flush=True)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
