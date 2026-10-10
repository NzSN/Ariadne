"""Regression checks for measurement production and full Windows I4 decisions."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_investigation as gate
import measure_investigation as measurement
from investigation_windows_case import load_case, case_digest


CASE = load_case()
LINUX = json.loads((gate.ROOT / "evidence/Ariadne/priority-1-real-capture-case.json").read_text())
ACTIVE_HISTORICAL = {"id": "historical-test-double", "capture": {**LINUX["capture"], "platform": "linux"},
                     "query": LINUX["query"], "expectations": {"decodedStarts": 34, "phaseBudgetMs": 250}}



def workload(median=1999):
    return {
        "schema": "ariadne.investigation-workload/v3",
        "passed": True,
        "sourcesStable": True,
        "toolsStable": True, "analysisBackend": "bap",
        "windowsCaseId": CASE["id"], "windowsCaseDigest": case_digest(CASE),
        "profile": "release",
        "warmups": 1,
        "repeats": 5,
        "windows98Checked": True,
        "windows98BudgetMs": 2000,
        "records": [{
            "workload": "real-windows-98", "mode": "explanation",
            "analysisBackend": "bap", "decodedStarts": 98,
            "artifactSha256": CASE["capture"]["sha256"],
            "identity": {"artifact_sha256": CASE["capture"]["sha256"], "query_id": "a" * 64},
            "query": {"entries": [CASE["query"]["entry_va"]], "seeds": [CASE["query"]["seed_va"]]},
            "question": {"site": CASE["query"]["seed_va"], "memory_access": 0},
            "outputSha256": "b" * 64,
            "warmupSamplesMs": [median], "elapsedSamplesMs": [median] * 5,
            "elapsedMs": {"median": median, "min": median, "max": median, "samples": 5},
        }],
    }


class InvestigationBudgetTests(unittest.TestCase):
    def acceptance(self, data, *, failure=False, stable=True):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            nested = work / "workload.json"
            nested.write_text(json.dumps(data))
            other = work / "other.json"
            other.write_text('{"passed": true}')

            def run(command, **kwargs):
                record = nested if command[-1] == "tools/measure_investigation.py" else other
                code = 1 if failure and command[:2] == ["cargo", "test"] else 0
                return subprocess.CompletedProcess(command, code, f"Report: {record}\n", "")

            with patch.object(gate, "sources", side_effect=[{"source": "before"}, {"source": "before" if stable else "after"}]), \
                 patch.object(gate, "active_identity", return_value=None), \
                 patch.object(gate, "sha", return_value="c" * 64), \
                 patch.object(gate.subprocess, "run", side_effect=run), \
                 patch.object(gate.tempfile, "mkdtemp", return_value=str(work)), \
                 patch("sys.argv", ["check_investigation.py"]), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    gate.main()
            report = json.loads((work / "report.json").read_text())
            self.assertEqual(result.exception.code, 0 if report["passed"] else 1)
            return report

    def test_full_acceptance_requires_windows_explanation_cli_budget(self):
        for median, expected in ((1999, True), (2000, True), (2000.01, False), (9000, False)):
            with self.subTest(median=median):
                data = workload(median)
                # A fast base-mode query cannot substitute for the explanation CLI.
                base = copy.deepcopy(data["records"][0])
                base.update(mode="base", elapsedSamplesMs=[1] * 5)
                data["records"].append(base)
                report = self.acceptance(data)
                self.assertTrue(report["passed"])
                self.assertEqual(report["fullI4RealCaptureAcceptance"], expected)
                self.assertEqual(bool(report["missing"]), not expected)

    def test_incomplete_or_invalid_windows_measurements_never_qualify(self):
        variants = []
        absent = workload()
        absent.update(windows98Checked=False, records=[])
        variants.append(absent)
        old = workload()
        old["schema"] = "ariadne.investigation-workload/v1"
        variants.append(old)
        for field, value in (("mode", "base"), ("workload", "stage-b-windows"),
                             ("analysisBackend", "rust"), ("decodedStarts", 2),
                             ("artifactSha256", "0" * 64), ("elapsedSamplesMs", [1] * 4),
                             ("elapsedSamplesMs", [-1] * 5), ("elapsedSamplesMs", [float("nan")] * 5),
                             ("elapsedSamplesMs", [float("inf")] * 5),
                             ("elapsedSamplesMs", [True] * 5), ("warmupSamplesMs", []),
                             ("outputSha256", "not-a-digest")):
            data = workload()
            data["records"][0][field] = value
            variants.append(data)
        for field, value in (("profile", "debug"), ("warmups", 0), ("repeats", 4),
                             ("windows98BudgetMs", 10000), ("sourcesStable", False),
                             ("toolsStable", False), ("windowsCaseId", "original-electron"),
                             ("windowsCaseDigest", "0" * 64)):
            data = workload()
            data[field] = value
            variants.append(data)
        for field in ("entries", "seeds"):
            data = workload()
            data["records"][0]["query"][field] = ["0x0000000000001000"]
            variants.append(data)
        for field, value in (("site", "0x0000000000001000"), ("memory_access", 1), ("memory_access", False)):
            data = workload()
            data["records"][0]["question"][field] = value
            variants.append(data)
        data = workload()
        data["records"][0]["identity"]["artifact_sha256"] = "0" * 64
        variants.append(data)
        data = workload(9000)
        data["records"][0]["elapsedMs"]["median"] = 1
        data["windows98TargetMet"] = True
        variants.append(data)
        data = workload()
        data["records"].append(copy.deepcopy(data["records"][0]))
        variants.append(data)
        for index, data in enumerate(variants):
            with self.subTest(case=index):
                report = self.acceptance(data)
                self.assertFalse(report["fullI4RealCaptureAcceptance"])
                self.assertTrue(report["missing"])

    def test_fast_timing_cannot_override_gate_or_source_failure(self):
        for failure, stable in ((True, True), (False, False)):
            with self.subTest(failure=failure, stable=stable):
                report = self.acceptance(workload(), failure=failure, stable=stable)
                self.assertFalse(report["passed"])
                self.assertFalse(report["fullI4RealCaptureAcceptance"])
                self.assertTrue(report["missing"])

    def test_measurement_runner_records_and_enforces_actual_samples(self):
        for median, expected in ((2000, True), (9000, False)):
            with self.subTest(median=median), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                dump = work / "windows98.dmp"
                dump.write_bytes(b"\0" * CASE["capture"]["bytes"])

                def sha(path):
                    if Path(path) == dump:
                        return CASE["capture"]["sha256"]
                    if Path(path).name == "chromium-member-uaf.dmp":
                        return LINUX["capture"]["sha256"]
                    return "d" * 64

                def run(command):
                    args = [str(x) for x in command]
                    if args[0] == "cargo":
                        return subprocess.CompletedProcess(args, 0, "", "")
                    if args[0] == "/usr/bin/time":
                        capture = Path(args[6])
                        entry = args[args.index("--entry") + 1]
                        site = args[args.index("--seed") + 1]
                        output = Path(args[args.index("--output-dir") + 1])
                        output.mkdir()
                        Path(args[4]).write_text("9,1024\n")
                        identity = {"artifact_sha256": sha(capture), "query_id": "a" * 64}
                        query = {"entries": [f"0x{int(entry, 16):016x}"], "seeds": [f"0x{int(site, 16):016x}"]}
                        (output / "report.json").write_text(json.dumps({"identity": identity, "query": query, "analysis": {"decoded": ["0x0"] * (98 if capture==dump else 4)}, "analysis_backend": {"backend": "bap"}}))
                        if "--explain-fault-address" in args:
                            producer = (CASE if capture == dump else LINUX)["query"]["producer_va"] if capture == dump or capture.name == "chromium-member-uaf.dmp" else f"0x{int(entry, 16) + (3 if capture.name == 'bap_precision_linux.dmp' else 0):016x}"
                            (output / "explanation.json").write_text(json.dumps({"identity": identity, "question": {"site": query["seeds"][0], "memory_access": 0}, "origins": [{"producers": [{"site": producer}]}], "claims": []}))
                        return subprocess.CompletedProcess(args, 0, "", "")
                    header = "artifact_sha256,binding_ns,explanation_ns,render_ns,claims,evidence,gaps\n"
                    body = (sha(args[1]) + ",1000000,1000000,1000000,1,1,1\n") * 6
                    return subprocess.CompletedProcess(args, 0, header + body, "")

                ticks = iter(n * median * 1_000_000 for n in range(120))
                with patch.object(measurement.real_case, "load_case", return_value=ACTIVE_HISTORICAL), \
                     patch.object(measurement.real_case, "selected_dump", return_value=measurement.ROOT / "tmp/priority1/chromium-member-uaf.dmp"), \
                     patch.object(measurement.real_case, "validate_report"), \
                     patch.object(measurement, "sources", return_value={"source": "digest"}), \
                     patch.object(measurement, "materialize", return_value=dump), \
                     patch.object(measurement, "native_manifest", return_value={"schema": "test"}), \
                     patch.object(measurement, "validate_backend_receipt"), \
                     patch.object(measurement, "active_identity", return_value=None), \
                     patch.object(measurement, "sha", side_effect=sha), \
                     patch.object(measurement, "run", side_effect=run), \
                     patch.object(measurement.time, "perf_counter_ns", side_effect=lambda: next(ticks)), \
                     patch.object(measurement.tempfile, "mkdtemp", return_value=str(work)), \
                     patch("sys.argv", ["measure_investigation.py", "--windows-dump", str(dump)]), \
                     redirect_stdout(io.StringIO()):
                    measurement.main()
                report = json.loads((work / "report.json").read_text())
                self.assertEqual(report["schema"], "ariadne.investigation-workload/v3")
                self.assertEqual(report["windows98Qualification"]["targetMet"], expected)
                self.assertEqual(report["windows98Qualification"]["medianMs"], median)
                self.assertEqual(self.acceptance(report)["fullI4RealCaptureAcceptance"], expected)


if __name__ == "__main__":
    unittest.main()
