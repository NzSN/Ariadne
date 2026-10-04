"""Pure tests for controlled Windows BAP workload records; no capture evidence."""
import copy
import statistics
import unittest

from bap_workload_contract import (
    WINDOWS_ARCHIVE_RELATIVE, WINDOWS_BUDGET_MS, WORKLOAD_SCHEMA, windows_qualification,
)


CASE = {
    "schema": "ariadne.bap-windows-workload-case/v1",
    "id": "crashpad-windows-checksum-98-v1",
    "captureKind": "controlled-crashpad-windows",
    "capture": {"sha256": "e" * 64, "bytes": 4096},
    "query": {
        "entry_va": "0x0000000140001000",
        "seed_va": "0x0000000140001040",
        "producer_va": "0x000000014000103c",
    },
    "expectations": {"decodedStarts": 98, "windowsBudgetMs": None, "timingPolicy": "unlimited"},
    "inputArchive": {
        "path": "evidence/Ariadne/bap-windows-workload-inputs.tar.gz",
        "sha256": "f" * 64,
        "captureMember": "capture.dmp",
    },
}
HISTORICAL_CAPTURE_SHA256 = "4b3deb70134015ec227b3cf5edf82e1dac0b308b3f19ae62f79cbd4251109e86"


def workload(samples=None, warmup_samples=None):
    samples = [1999] * 5 if samples is None else samples
    warmup_samples = [3000] if warmup_samples is None else warmup_samples
    return {
        "schema": WORKLOAD_SCHEMA,
        "passed": True,
        "sourcesStable": True,
        "sourceHashes": {
            "tools/measure_bap.py": "d" * 64,
            WINDOWS_ARCHIVE_RELATIVE: CASE["inputArchive"]["sha256"],
        },
        "profile": "release",
        "warmups": len(warmup_samples),
        "repeats": len(samples),
        "semanticBackend": "bap-only",
        "llvmSemanticFallback": False,
        "windowsWorkloadChecked": True,
        "windowsWorkloadBudgetMs": WINDOWS_BUDGET_MS,
        "windowsWorkloadTimingPolicy": "unlimited",
        "records": [{
            "workload": CASE["id"],
            "backend": "bap",
            "captureKind": CASE["captureKind"],
            "historicalCapture": False,
            "artifactSha256": CASE["capture"]["sha256"],
            "entry": CASE["query"]["entry_va"],
            "seed": CASE["query"]["seed_va"],
            "identity": {
                "artifact_sha256": CASE["capture"]["sha256"],
                "query_id": "a" * 64,
                "platform": "windows",
                "decoder_target": "x86_64-pc-windows-msvc",
            },
            "query": {"entries": [CASE["query"]["entry_va"]], "seeds": [CASE["query"]["seed_va"]]},
            "reportSha256": {name: "b" * 64 for name in ("report.json", "report.txt", "report.dot")},
            "counts": {"decoded": 98, "edges": 100, "slice": 9, "obligations": 0},
            "warmupSamplesMs": warmup_samples,
            "elapsedSamplesMs": samples,
            "elapsedMs": {"median": statistics.median(samples), "min": min(samples),
                          "max": max(samples), "samples": len(samples)},
        }],
    }


class BapWorkloadContractTests(unittest.TestCase):
    def assert_invalid(self, data, case=CASE):
        result = windows_qualification(data, case)
        self.assertEqual(result["status"], "invalid")
        self.assertFalse(result["valid"])
        self.assertFalse(result["targetMet"])
        self.assertIsNone(result["budgetMs"])
        self.assertTrue(result["reason"])

    def test_current_schema_is_v4(self):
        self.assertEqual(WORKLOAD_SCHEMA, "ariadne.bap-workloads/v4")

    def test_unlimited_policy_keeps_raw_medians_without_latency_rejection(self):
        for samples, median, met in (([0] * 5, 0, True), ([1999] * 5, 1999, True),
                                     ([2000] * 5, 2000, True), ([2000.01] * 5, 2000.01, True),
                                     ([9000] * 5, 9000, True), ([1e12] * 5, 1e12, True),
                                     ([9000, 1998, 2000, 1999, 3000, 0], 1999.5, True)):
            with self.subTest(samples=samples):
                data = workload(samples, [10000, 9000])
                data.update(windowsWorkloadTargetMet=not met, defaultPromotionEligible=not met,
                            windowsWorkloadQualification={"valid": True, "targetMet": not met, "medianMs": 0})
                result = windows_qualification(data, CASE)
                self.assertTrue(result["checked"])
                self.assertTrue(result["valid"])
                self.assertEqual(result["targetMet"], met)
                self.assertEqual(result["status"], "unlimited")
                self.assertEqual(result["medianMs"], median)
                self.assertEqual(result["samples"], len(samples))

    def test_manifest_must_explicitly_authorize_unlimited_timing(self):
        for field, value in (("windowsBudgetMs", 2000), ("windowsBudgetMs", float("inf")),
                             ("timingPolicy", "bounded"), ("timingPolicy", None)):
            case = copy.deepcopy(CASE)
            case["expectations"][field] = value
            self.assert_invalid(workload([1e12] * 5), case)
        for field in ("windowsBudgetMs", "timingPolicy"):
            case = copy.deepcopy(CASE)
            del case["expectations"][field]
            self.assert_invalid(workload(), case)

    def test_absent_windows_is_unavailable(self):
        for data in ({}, {"windowsWorkloadChecked": False},
                     {"windowsWorkloadChecked": False, "records": [{"workload": "stage-b-windows"}]}):
            with self.subTest(data=data):
                result = windows_qualification(data, CASE)
                self.assertEqual(result["status"], "unavailable")
                self.assertFalse(result["checked"])
                self.assertFalse(result["valid"])
                self.assertFalse(result["targetMet"])
                self.assertIsNone(result["medianMs"])
                self.assertEqual(result["samples"], 0)

    def test_malformed_workload_and_windows_flag_are_invalid(self):
        for data in (None, [], "record", 1):
            with self.subTest(data=data):
                self.assert_invalid(data)
        for flag in (None, 0, 1, "true", [], {}):
            with self.subTest(flag=flag):
                data = workload()
                data["windowsWorkloadChecked"] = flag
                self.assert_invalid(data)
        data = workload()
        data["windowsWorkloadChecked"] = False
        self.assert_invalid(data)

    def test_required_top_level_fields_are_strict(self):
        variants = {
            "schema": [None, "ariadne.bap-workloads/v1", "ariadne.bap-workloads/v2", "ariadne.bap-workloads/v3"],
            "passed": [False, 1, "true"], "sourcesStable": [False, 1, "true"],
            "windowsWorkloadTimingPolicy": [None, "bounded", True],
            "profile": [None, "debug"], "windowsWorkloadBudgetMs": [2000, 2000.0, True, 1999, 10000, float("inf"), "unlimited"],
            "semanticBackend": [None, "llvm", "bap"], "llvmSemanticFallback": [True, 0, "false"],
            "repeats": [0, 4, True, 5.0], "warmups": [0, True, 1.0],
            "records": [None, {}, [None], [], [{"workload": "stage-b-windows"}]],
        }
        for field, values in variants.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    data = workload()
                    data[field] = value
                    self.assert_invalid(data)
        for field in workload():
            with self.subTest(missing=field):
                data = workload()
                del data[field]
                self.assert_invalid(data)

    def test_source_hash_map_requires_canonical_digests(self):
        for value in (None, [], {}, {"source": "digest"}, {"source": "A" * 64},
                      {"source": "a" * 63}, {"source": 1}, {"": "a" * 64}, {1: "a" * 64}):
            with self.subTest(sourceHashes=value):
                data = workload()
                data["sourceHashes"] = value
                self.assert_invalid(data)

    def test_windows_archive_source_digest_must_match_manifest(self):
        for digest in (None, "0" * 64):
            with self.subTest(archive_digest=digest):
                data = workload()
                if digest is None:
                    del data["sourceHashes"][WINDOWS_ARCHIVE_RELATIVE]
                else:
                    data["sourceHashes"][WINDOWS_ARCHIVE_RELATIVE] = digest
                self.assert_invalid(data)
                self.assertIn("archive digest", windows_qualification(data, CASE)["reason"])
                data.update(windowsWorkloadChecked=False, records=[])
                self.assertEqual(windows_qualification(data, CASE)["status"], "unavailable")

    def test_exact_controlled_workload_and_bap_backend_are_required(self):
        for field, values in {
            "workload": [None, "stage-b-windows", "real-windows", "real-windows-98"],
            "backend": [None, "llvm", "bap-only"],
            "captureKind": [None, "historical-windows", "controlled", True],
            "historicalCapture": [None, True, 0, 1, "false"],
            "artifactSha256": [None, "0" * 64, CASE["capture"]["sha256"].upper(),
                               HISTORICAL_CAPTURE_SHA256],
            "entry": [None, "0x7ff6451d52d0", "0x0000000000001000"],
            "seed": [None, "0x7ff6451d530f", "0x0000000000001000"],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    data = workload()
                    data["records"][0][field] = value
                    self.assert_invalid(data)
        for backend in ("bap", "llvm"):
            with self.subTest(duplicate_backend=backend):
                data = workload()
                duplicate = copy.deepcopy(data["records"][0])
                duplicate["backend"] = backend
                data["records"].append(duplicate)
                self.assert_invalid(data)

    def test_legacy_capture_cannot_be_relabelled_as_the_current_capture(self):
        data = workload()
        data["records"][0]["artifactSha256"] = HISTORICAL_CAPTURE_SHA256
        data["records"][0]["identity"]["artifact_sha256"] = HISTORICAL_CAPTURE_SHA256
        self.assert_invalid(data)

    def test_legacy_fields_and_flags_cannot_qualify_old_records(self):
        for schema in ("ariadne.bap-workloads/v1", "ariadne.bap-workloads/v2"):
            with self.subTest(schema=schema):
                data = workload()
                data["schema"] = schema
                data["windows98Checked"] = data.pop("windowsWorkloadChecked")
                data["windows98BudgetMs"] = data.pop("windowsWorkloadBudgetMs")
                data.update(windows98TargetMet=True, defaultPromotionEligible=True,
                            windows98Qualification={"valid": True, "targetMet": True})
                data["records"][0].update(workload="real-windows-98", historicalCapture=True)
                result = windows_qualification(data, CASE)
                self.assertFalse(result["valid"])
                self.assertFalse(result["targetMet"])

    def test_artifact_query_and_target_identity_are_bound(self):
        for field, values in {
            "artifact_sha256": [None, "0" * 64], "query_id": [None, "bad", "a" * 63, "A" * 64, 1],
            "platform": [None, "linux"], "decoder_target": [None, "x86_64-unknown-linux-gnu"],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    data = workload()
                    data["records"][0]["identity"][field] = value
                    self.assert_invalid(data)
        for field in ("entries", "seeds"):
            for value in (None, [], ["0x0000000000001000"], CASE["query"]["entry_va"], [True]):
                with self.subTest(field=field, value=value):
                    data = workload()
                    data["records"][0]["query"][field] = value
                    self.assert_invalid(data)
        for field in ("identity", "query"):
            for value in (None, [], "bound"):
                with self.subTest(field=field, value=value):
                    data = workload()
                    data["records"][0][field] = value
                    self.assert_invalid(data)

    def test_all_report_hashes_are_required(self):
        for name in ("report.json", "report.txt", "report.dot"):
            for value in (None, "", "a" * 63, "A" * 64, 1):
                with self.subTest(name=name, value=value):
                    data = workload()
                    data["records"][0]["reportSha256"][name] = value
                    self.assert_invalid(data)
        for value in (None, [], {}):
            with self.subTest(reportSha256=value):
                data = workload()
                data["records"][0]["reportSha256"] = value
                self.assert_invalid(data)

    def test_counts_require_exact_manifest_count_and_nonnegative_integers(self):
        for name in ("decoded", "edges", "slice", "obligations"):
            for value in (None, -1, True, 64.0, "64"):
                with self.subTest(name=name, value=value):
                    data = workload()
                    data["records"][0]["counts"][name] = value
                    self.assert_invalid(data)
        for decoded in (0, 63, 64, 97, 99):
            with self.subTest(decoded=decoded):
                data = workload()
                data["records"][0]["counts"]["decoded"] = decoded
                self.assert_invalid(data)
        data = workload()
        data["records"][0]["counts"]["decoded"] = 98
        self.assertTrue(windows_qualification(data, CASE)["valid"])
        for value in (None, [], {}):
            data["records"][0]["counts"] = value
            self.assert_invalid(data)

    def test_raw_samples_are_finite_nonnegative_numbers_with_exact_counts(self):
        for field in ("elapsedSamplesMs", "warmupSamplesMs"):
            for value in (None, -1, float("nan"), float("inf"), float("-inf"), True, "1", {}, 10 ** 1000):
                with self.subTest(field=field, value=value):
                    data = workload()
                    data["records"][0][field][0] = value
                    self.assert_invalid(data)
            for value in (None, (), [], [0, 0], "1999"):
                with self.subTest(field=field, samples=value):
                    data = workload()
                    data["records"][0][field] = value
                    self.assert_invalid(data)

    def test_tampered_summaries_cannot_override_raw_timings(self):
        for field in ("median", "min", "max", "samples"):
            for value in (None, 0, True, "1", float("nan"), float("inf")):
                with self.subTest(field=field, value=value):
                    data = workload([9000] * 5)
                    data.update(windowsWorkloadTargetMet=True, defaultPromotionEligible=True)
                    data["records"][0]["elapsedMs"][field] = value
                    self.assert_invalid(data)
        for value in (None, [], {}):
            data = workload()
            data["records"][0]["elapsedMs"] = value
            self.assert_invalid(data)
        data = workload()
        data["records"][0]["elapsedMs"]["samples"] = 5.0
        self.assert_invalid(data)

    def test_missing_record_fields_are_invalid(self):
        for field in workload()["records"][0]:
            with self.subTest(missing=field):
                data = workload()
                del data["records"][0][field]
                self.assert_invalid(data)

    def test_malformed_expected_case_fails_closed(self):
        for case in (None, [], {}, {"capture": [], "query": {}},
                     {"capture": {"sha256": "not-a-digest"}, "query": CASE["query"]}):
            with self.subTest(case=case):
                self.assert_invalid(workload(), case)
        for field, values in {
            "schema": [None, "ariadne-priority-4-real-capture-case-v1"],
            "id": [None, "real-windows-98", "different-controlled-case"],
            "captureKind": [None, "historical-windows", True],
            "capture": [None, [], {}], "query": [None, [], {}],
            "expectations": [None, [], {}], "inputArchive": [None, [], {}],
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    case = copy.deepcopy(CASE)
                    case[field] = value
                    self.assert_invalid(workload(), case)
        for section, field, values in (
            ("capture", "sha256", [None, "not-a-digest", "E" * 64]),
            ("capture", "bytes", [None, -1, 0, True, 4096.0, "4096"]),
            ("expectations", "decodedStarts", [None, 0, 63, 64, 97, 99, True, 98.0, "98"]),
            ("inputArchive", "path", [None, "capture.tar.gz", "../capture.tar.gz"]),
            ("inputArchive", "sha256", [None, "not-a-digest", "F" * 64]),
            ("inputArchive", "captureMember", [None, "other.dmp", "../capture.dmp"]),
        ):
            for value in values:
                with self.subTest(section=section, field=field, value=value):
                    case = copy.deepcopy(CASE)
                    case[section][field] = value
                    self.assert_invalid(workload(), case)
        for field in ("entry_va", "seed_va", "producer_va"):
            for value in (None, "0x140001000", "0X0000000140001000", True, 0x140001000):
                with self.subTest(field=field, value=value):
                    case = copy.deepcopy(CASE)
                    case["query"][field] = value
                    self.assert_invalid(workload(), case)
        for section, value in CASE.items():
            if isinstance(value, dict):
                for field in value:
                    with self.subTest(section=section, missing=field):
                        case = copy.deepcopy(CASE)
                        del case[section][field]
                        self.assert_invalid(workload(), case)
            else:
                with self.subTest(missing=section):
                    case = copy.deepcopy(CASE)
                    del case[section]
                    self.assert_invalid(workload(), case)

    def test_validation_does_not_mutate_supplied_evidence(self):
        data = workload()
        before = copy.deepcopy(data)
        case = copy.deepcopy(CASE)
        self.assertTrue(windows_qualification(data, case)["valid"])
        self.assertEqual(data, before)
        self.assertEqual(case, CASE)


if __name__ == "__main__":
    unittest.main()
