#!/usr/bin/env python3
"""Native-default source/tool-bound I5a measurements under the frozen contract."""
import csv
import hashlib
import io
import json
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

from i5a_native_contract import (
    PROFILE, environment, manifest_digest, native_manifest, sha, source_inventory,
    strict_json, tool_hashes, validate_backend_receipt, validate_performance_contract,
    validate_phase_rows,
)

ROOT = Path(__file__).resolve().parents[1]
sources = source_inventory


def run(command, env):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, env=env,
                            text=True, capture_output=True, timeout=240)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result


def main():
    before = sources()
    work = Path(tempfile.mkdtemp(prefix="ariadne-i5a-measurement-"))
    env = environment()
    contract = strict_json((ROOT / "tests/input/fixtures/i5a/performance.json").read_text())
    validate_performance_contract(contract)
    cases = {r["name"]: r for r in strict_json(
        (ROOT / "tests/input/fixtures/i5a/manifest.json").read_text())["cases"]}
    for binary, flags in [("ariadne-minidump", []), ("i5a", ["--features", "bench"])]:
        run(["cargo", "build", "--offline", "--locked", "--release", *flags, "--bin", binary], env)
    cli = ROOT / "target/release/ariadne-minidump"
    bench = ROOT / "target/release/i5a"
    decoder = ROOT / "target/ariadne-llvm-mc"
    manifest = native_manifest()
    tools_before = tool_hashes()
    rows, phases, records = [], [], []
    print("I5a measurement artifacts:", work, flush=True)
    for name in contract["cases"]:
        case = cases[name]
        dump = ROOT / "tests/input/fixtures/i5a" / f"{name}.dmp"
        if sha(dump) != case["sha256"]:
            raise RuntimeError("fixture identity mismatch")
        modes, expected_core, expected_receipt = {}, None, None
        question = {"site": f"0x{case['site']:016x}", "memory_access": 0}
        for mode in ["base", "assessment"]:
            samples, outputs = [], None
            for n in range(contract["warmups"] + contract["repeats"]):
                out = work / f"{name}-{mode}-{n}"
                timer = work / f"{name}-{mode}-{n}.time"
                command = [cli, dump, "--decoder-reference", decoder, "--entry", f"{case['site']:x}",
                           "--seed", f"{case['site']:x}", "--output-dir", out]
                if mode == "assessment":
                    command += ["--assess-zero-address", f"{case['site']:x}", "--memory-access", "0"]
                start = time.perf_counter_ns()
                run(["/usr/bin/time", "-f", "%e,%M", "-o", timer, *command], env)
                elapsed = (time.perf_counter_ns() - start) / 1e6
                hashes = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
                if outputs is not None and outputs != hashes:
                    raise RuntimeError("nonrepeatable output")
                outputs = hashes
                core = {p: hashes[p] for p in ["report.txt", "report.json", "report.dot"]}
                if expected_core is None:
                    expected_core = core
                elif expected_core != core:
                    raise RuntimeError("assessment changed original report bytes")
                report = strict_json((out / "report.json").read_text())
                receipt = validate_backend_receipt(report, manifest)
                if expected_receipt is None:
                    expected_receipt = receipt
                elif receipt != expected_receipt:
                    raise RuntimeError("backend query receipt changed")
                if (report["identity"]["artifact_sha256"] != case["sha256"]
                        or report["query"]["entries"] != [question["site"]]
                        or report["query"]["seeds"] != [question["site"]]):
                    raise RuntimeError("query identity changed")
                if mode == "assessment":
                    result = strict_json((out / "zero-address-assessment.json").read_text())
                    if (result["conclusion"] != case["outcome"] or result["question"] != question
                            or any(result["identity"][k] != report["identity"][k]
                                   for k in ["snapshot_id", "artifact_sha256", "query_id"])):
                        raise RuntimeError("independent assessment expectation failed")
                rss = int(timer.read_text().strip().split(",")[1])
                rows.append(dict(case=name, mode=mode, run=n, warmup=n < contract["warmups"],
                                 elapsed_ms=elapsed, rss_kib=rss, analysis_backend="bap",
                                 analysis_profile=PROFILE, artifact_sha256=case["sha256"],
                                 snapshot_id=receipt["snapshot"], query_id=report["identity"]["query_id"],
                                 backend_query=receipt["query"], manifest_sha256=manifest_digest(manifest)))
                if n >= contract["warmups"]:
                    samples.append(elapsed)
            # Explicit selection proves that the timed default ran the native
            # product path. This extra comparison is outside measured samples.
            explicit = work / f"{name}-{mode}-explicit-bap"
            explicit_command = list(command)
            explicit_command[explicit_command.index("--output-dir") + 1] = explicit
            run([*explicit_command, "--analysis-backend", "bap"], env)
            explicit_report = strict_json((explicit / "report.json").read_text())
            validate_backend_receipt(explicit_report, manifest)
            if {p.name: sha(p) for p in explicit.iterdir() if p.is_file()} != outputs:
                raise RuntimeError("default CLI differs from explicit BAP")
            modes[mode] = dict(samplesMs=samples, medianMs=statistics.median(samples),
                               minMs=min(samples), maxMs=max(samples), outputHashes=outputs,
                               explicitBapOutputHashes=outputs, defaultNativeVerified=True)
        output_sha256 = hashlib.sha256(b"".join(
            (out / ("zero-address-assessment." + suffix)).read_bytes()
            for suffix in ["txt", "json", "dot"])).hexdigest()
        raw = list(csv.DictReader(io.StringIO(run(
            [bench, dump, decoder, f"{case['site']:x}", f"{case['site']:x}",
             str(contract["warmups"] + contract["repeats"])], env).stdout)))
        conclusion = {"consistent_with_evidence": "ConsistentWithEvidence",
                      "refuted_under_premises": "RefutedUnderPremises", "unknown": "Unknown"}[case["outcome"]]
        samples = validate_phase_rows(raw, report, manifest, contract,
                                      conclusion=conclusion, output_sha256=output_sha256)
        phases.extend(dict(case=name, **row) for row in raw)
        passed = (statistics.median(samples) <= contract["phaseMedianBudgetMs"]
                  and modes["assessment"]["medianMs"] <= contract["cliMedianBudgetMs"])
        records.append(dict(case=name, artifactSha256=case["sha256"], query=report["query"],
                            reportIdentity=report["identity"], backendReceipt=receipt, modes=modes,
                            phaseSamplesMs=samples, phaseMedianMs=statistics.median(samples), passed=passed))
        print(name, "PASS" if passed else "OVER BUDGET", round(modes["assessment"]["medianMs"], 2),
              "ms CLI;", round(statistics.median(samples), 3), "ms phases", flush=True)
    for name, data in [("cli.csv", rows), ("phase.csv", phases)]:
        with (work / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(data)
    stable, tools_after = before == sources(), tool_hashes()
    report = dict(schema="ariadne.i5a-fixture-measurements/v2",
                  passed=stable and tools_before == tools_after and all(r["passed"] for r in records),
                  sourcesStable=stable, toolsStable=tools_before == tools_after,
                  sourceHashes=before, tools=tools_after, analysisBackend="bap", analysisProfile=PROFILE,
                  defaultNativeVerified=True, helperManifest=manifest, contract=contract,
                  host=platform.platform(), records=records,
                  csvSha256={p: sha(work / p) for p in ["cli.csv", "phase.csv"]},
                  controlledRealWindowsAcceptancePassed=False, originalWindowsI4AcceptancePassed=False,
                  scope=contract["scope"])
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Report:", work / "report.json", flush=True)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
