"""Controlled main() regressions; subprocesses do not run native acceptance."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_bap_semantics as gate
from bap_workload_contract import WINDOWS_ARCHIVE_RELATIVE
from test_bap_workload_contract import CASE, HISTORICAL_CAPTURE_SHA256, workload as contract_workload


FULL_GATE_FIELDS = (
    "stage1ExitPassed", "stage2PrerequisiteSatisfied", "defaultPromotionEligible",
)
SOURCE_HASHES = {name: "c" * 64 for name in ("src/engine.rs", "tools/measure_bap.py")}
SOURCE_HASHES[WINDOWS_ARCHIVE_RELATIVE] = CASE["inputArchive"]["sha256"]
TOOL_HASHES = {name: "c" * 64 for name in (
    "target/release/ariadne-minidump", "target/release/bap_minidump",
    "target/ariadne-llvm-mc", "target/ariadne-bap-lift",
    "native/bap/toolchain.lock.json", "tools/measure_bap.py",
)}


def workload(samples=None):
    data = contract_workload(samples)
    data.update(sourceHashes=dict(SOURCE_HASHES), tools=dict(TOOL_HASHES))
    return data


class BapWorkloadGateTests(unittest.TestCase):
    def acceptance(self, data, *, failure=False, stable=True, reuse=False, case=CASE,
                   source_hashes=None):
        """Run the real decision with controlled source, tool and command results."""
        current_sources = dict(SOURCE_HASHES if source_hashes is None else source_hashes)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            nested = work / "workload.json"
            nested.write_text(json.dumps(data))
            manifest = work / "controlled-windows-case.json"
            manifest.write_text(json.dumps(case))
            other = work / "other.json"
            other.write_text('{"passed": true}')
            argv = ["check_bap_semantics.py"]
            if reuse:
                argv += ["--workload-record", str(nested)]

            def run(command, **kwargs):
                record = nested if command == ["python3", "tools/measure_bap.py"] else other
                code = 1 if failure and command[:2] == ["cargo", "test"] else 0
                return subprocess.CompletedProcess(command, code, f"Report: {record}\n", "")

            with patch.object(gate, "sources", side_effect=[
                {"source": "before"}, {"source": "before" if stable else "after"},
            ]), patch.object(gate, "workload_sources", return_value=current_sources, create=True), \
                 patch.object(gate, "WINDOWS_CASE_PATH", manifest), \
                 patch.object(gate, "sha", return_value="c" * 64), \
                 patch.object(gate.subprocess, "run", side_effect=run) as commands, \
                 patch.object(gate.tempfile, "mkdtemp", return_value=str(work)), \
                 patch("sys.argv", argv), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    gate.main()
            report = json.loads((work / "report.json").read_text())
            self.assertEqual(result.exception.code, 0 if report["passed"] else 1)
            self.assertEqual(any(call.args[0] == ["python3", "tools/measure_bap.py"]
                                 for call in commands.call_args_list), not reuse)
            return report

    def assert_qualification(self, report, expected, *, implemented=True):
        self.assertEqual(report["schema"], "ariadne.bap-only-removal/v5")
        self.assertIs(report["passed"], implemented)
        self.assertIs(report["implementationGatesPassed"], implemented)
        for field in FULL_GATE_FIELDS:
            with self.subTest(field=field):
                self.assertIs(report[field], expected)
        self.assertEqual(bool(report["missing"]), not expected)
        self.assertFalse(report["stage2Started"])
        self.assertFalse(report["stage2Qualified"])
        self.assertIn("windowsWorkloadQualification", report)
        self.assertNotIn("windows98Qualification", report)

    def test_full_gates_accept_any_finite_latency_under_unlimited_policy(self):
        for median, expected in ((1999, True), (2000, True), (2000.01, True), (9000, True), (1e12, True)):
            with self.subTest(median=median):
                data = workload([median] * 5)
                data.update(windowsWorkloadTargetMet=True, defaultPromotionEligible=True)
                self.assert_qualification(self.acceptance(data), expected)

    def test_valid_raw_evidence_does_not_require_producer_qualification_flags(self):
        for producer_flag in (None, False):
            with self.subTest(producer_flag=producer_flag):
                data = workload()
                if producer_flag is not None:
                    data.update(windowsWorkloadTargetMet=producer_flag,
                                defaultPromotionEligible=producer_flag)
                self.assert_qualification(self.acceptance(data), True)

    def test_missing_or_old_windows_evidence_cannot_qualify(self):
        variants = []
        absent = workload()
        absent.update(windowsWorkloadChecked=False, records=[])
        variants.append(("not-exercised", absent))
        omitted = workload()
        del omitted["windowsWorkloadChecked"]
        variants.append(("missing-check-flag", omitted))
        for schema in ("ariadne.bap-workloads/v1", "ariadne.bap-workloads/v2"):
            old = workload()
            old["schema"] = schema
            variants.append((schema, old))
            legacy = workload()
            legacy["schema"] = schema
            legacy["windows98Checked"] = legacy.pop("windowsWorkloadChecked")
            legacy["windows98BudgetMs"] = legacy.pop("windowsWorkloadBudgetMs")
            legacy.update(windows98TargetMet=True,
                          windows98Qualification={"valid": True, "targetMet": True})
            legacy["records"][0].update(workload="real-windows-98", historicalCapture=True)
            variants.append((f"legacy-fields-{schema}", legacy))
        no_record = workload()
        no_record["records"] = []
        variants.append(("missing-record", no_record))
        missing_samples = workload()
        del missing_samples["records"][0]["elapsedSamplesMs"]
        variants.append(("missing-raw-samples", missing_samples))
        for reuse in (False, True):
            for name, data in variants:
                with self.subTest(case=name, reuse=reuse):
                    data.update(windowsWorkloadTargetMet=True, defaultPromotionEligible=True)
                    self.assert_qualification(self.acceptance(data, reuse=reuse), False)

    def test_malformed_windows_data_cannot_qualify(self):
        variants = []
        for field, value in (
            ("workload", "stage-b-windows"), ("workload", "real-windows-98"),
            ("backend", "llvm"), ("captureKind", "historical-windows"),
            ("captureKind", None), ("historicalCapture", True), ("historicalCapture", 0),
            ("artifactSha256", "0" * 64), ("artifactSha256", HISTORICAL_CAPTURE_SHA256),
            ("entry", "0x0000000000001000"), ("seed", "0x0000000000001000"),
            ("identity", None), ("query", []), ("reportSha256", {}),
            ("counts", {"decoded": 63, "edges": 100, "slice": 9, "obligations": 0}),
            ("counts", {"decoded": 97, "edges": 100, "slice": 9, "obligations": 0}),
            ("counts", {"decoded": 99, "edges": 100, "slice": 9, "obligations": 0}),
            ("elapsedSamplesMs", [1999] * 4), ("elapsedSamplesMs", [-1] * 5),
            ("elapsedSamplesMs", [float("nan")] * 5),
            ("elapsedSamplesMs", [float("inf")] * 5),
            ("elapsedSamplesMs", [True] * 5), ("warmupSamplesMs", []),
        ):
            data = workload()
            data["records"][0][field] = value
            variants.append((f"record-{field}-{value}", data))
        for field, value in (
            ("profile", "debug"), ("repeats", 4), ("warmups", 0),
            ("windowsWorkloadChecked", 1), ("windowsWorkloadBudgetMs", 10000),
            ("semanticBackend", "llvm"),
            ("llvmSemanticFallback", True),
        ):
            data = workload()
            data[field] = value
            variants.append((f"workload-{field}", data))
        for field in ("entries", "seeds"):
            data = workload()
            data["records"][0]["query"][field] = ["0x0000000000001000"]
            variants.append((f"query-{field}", data))
        wrong_identity = workload()
        wrong_identity["records"][0]["identity"]["artifact_sha256"] = "0" * 64
        variants.append(("identity-artifact", wrong_identity))
        old_capture = workload()
        old_capture["records"][0]["artifactSha256"] = HISTORICAL_CAPTURE_SHA256
        old_capture["records"][0]["identity"]["artifact_sha256"] = HISTORICAL_CAPTURE_SHA256
        variants.append(("relabeled-historical-capture", old_capture))
        duplicate = workload()
        duplicate["records"].append(copy.deepcopy(duplicate["records"][0]))
        variants.append(("duplicate-windows", duplicate))
        for name, data in variants:
            with self.subTest(case=name):
                data.update(windowsWorkloadTargetMet=True, defaultPromotionEligible=True)
                self.assert_qualification(self.acceptance(data), False)

    def test_manifest_mismatch_cannot_qualify_otherwise_valid_workload(self):
        for section, field, value in (
            ("capture", "sha256", "0" * 64),
            ("query", "entry_va", "0x0000000140002000"),
            ("query", "seed_va", "0x0000000140002040"),
            ("query", "producer_va", "0x14000103c"),
            ("expectations", "decodedStarts", 97),
            ("inputArchive", "sha256", "invalid"),
        ):
            with self.subTest(section=section, field=field):
                case = copy.deepcopy(CASE)
                case[section][field] = value
                self.assert_qualification(self.acceptance(workload(), case=case), False)

    def test_forged_summary_and_producer_flags_cannot_override_raw_samples(self):
        data = workload([9000] * 5)
        data.update(windowsWorkloadTargetMet=True, defaultPromotionEligible=True,
                    windowsWorkloadQualification={"valid": True, "targetMet": True, "medianMs": 1})
        data["records"][0]["elapsedMs"].update(median=1, min=1, max=1)
        self.assert_qualification(self.acceptance(data), False)

    def test_fast_valid_timing_cannot_override_gate_or_source_failure(self):
        for failure, stable in ((True, True), (False, False), (True, False)):
            with self.subTest(failure=failure, stable=stable):
                data = workload()
                data.update(windowsWorkloadTargetMet=True, defaultPromotionEligible=True)
                self.assert_qualification(self.acceptance(data, failure=failure, stable=stable),
                                          False, implemented=False)

    def test_valid_workload_bindings_qualify_fresh_and_retained_records(self):
        for reuse in (False, True):
            with self.subTest(reuse=reuse):
                self.assert_qualification(self.acceptance(workload(), reuse=reuse), True)

    def test_current_archive_inventory_must_match_manifest_for_qualification(self):
        current_sources = dict(SOURCE_HASHES)
        current_sources[WINDOWS_ARCHIVE_RELATIVE] = "0" * 64
        for reuse in (False, True):
            with self.subTest(reuse=reuse):
                data = workload()
                data["sourceHashes"] = dict(current_sources)
                report = self.acceptance(data, reuse=reuse, source_hashes=current_sources)
                self.assert_qualification(report, False, implemented=True)
                qualification = report["windowsWorkloadQualification"]
                self.assertEqual(qualification["status"], "invalid")
                self.assertIn("archive digest", qualification["reason"])

    def test_nonpassing_or_unstable_workloads_fail_fresh_and_retained_gates(self):
        for reuse in (False, True):
            for field in ("passed", "sourcesStable"):
                for value in (False, 1, "true"):
                    with self.subTest(reuse=reuse, field=field, value=value):
                        data = workload()
                        data[field] = value
                        self.assert_qualification(self.acceptance(data, reuse=reuse),
                                                  False, implemented=False)

    def test_incomplete_or_malformed_source_bindings_fail_fresh_and_retained_gates(self):
        variants = [("missing", None), ("empty", {}), ("null", None),
                    ("list", []), ("string", "sources"),
                    ("truncated", {"tools/measure_bap.py": "c" * 64})]
        stale = dict(SOURCE_HASHES)
        stale["src/engine.rs"] = "d" * 64
        variants.append(("stale", stale))
        extra = dict(SOURCE_HASHES)
        extra["unreviewed.rs"] = "c" * 64
        variants.append(("extra", extra))
        for reuse in (False, True):
            for name, bindings in variants:
                with self.subTest(reuse=reuse, bindings=name):
                    data = workload()
                    if name == "missing":
                        del data["sourceHashes"]
                    else:
                        data["sourceHashes"] = bindings
                    self.assert_qualification(self.acceptance(data, reuse=reuse),
                                              False, implemented=False)

    def test_incomplete_or_malformed_tool_bindings_fail_fresh_and_retained_gates(self):
        variants = [("missing", None), ("empty", {}), ("null", None),
                    ("list", []), ("string", "tools")]
        for path in TOOL_HASHES:
            incomplete = dict(TOOL_HASHES)
            del incomplete[path]
            variants.append((f"missing-{path}", incomplete))
            stale = dict(TOOL_HASHES)
            stale[path] = "d" * 64
            variants.append((f"stale-{path}", stale))
        extra = dict(TOOL_HASHES)
        extra["unreviewed-tool"] = "c" * 64
        variants.append(("extra", extra))
        for reuse in (False, True):
            for name, bindings in variants:
                with self.subTest(reuse=reuse, bindings=name):
                    data = workload()
                    if name == "missing":
                        del data["tools"]
                    else:
                        data["tools"] = bindings
                    self.assert_qualification(self.acceptance(data, reuse=reuse),
                                              False, implemented=False)


if __name__ == "__main__":
    unittest.main()
