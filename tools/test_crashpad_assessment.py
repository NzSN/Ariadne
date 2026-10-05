#!/usr/bin/env python3
"""Controlled-capture acceptance regressions using synthetic provenance files.

These tests exercise rejection and binding rules without asserting that the
fabricated inputs are native Windows captures or a qualification corpus.
"""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import i5a_native_contract as NATIVE

SPEC = importlib.util.spec_from_file_location(
    "crashpad_assessment", ROOT / "native/crashpad-demo/assess.py")
ASSESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ASSESS)

ENTRY = "0x0000000140001000"
SITE = "0x0000000140001004"
OTHER_SHA = "f" * 64


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def performance_contract():
    return {"schema": "ariadne.i5a-performance-contract/v1", "profile": "release",
            "warmups": 1, "repeats": 5, "phaseMedianBudgetMs": 10,
            "cliMedianBudgetMs": 1500}


def report_fixture():
    manifest = {"schema": "ariadne.bap-core-build/v1",
                "helper_sha256": digest(b"native helper"),
                "handshake": {"schema": "ariadne.bap-core-ready/v1", "abi": 2}}
    artifact = digest(b"captured dump")
    snapshot = "minidump-captured-amd64-v1:" + artifact
    limits = dict(max_starts=4096, max_candidates=8192, max_prefix_bytes=61440,
                  max_decoder_batches=4096, batch_size=128)
    # Independently assemble this fixture's public query identity. The native
    # receipt has a different query digest; both must survive validation.
    query_bytes = b"ariadne-minidump-query-v1\0" + snapshot.encode()
    for value in (ENTRY, SITE):
        query_bytes += (1).to_bytes(8, "little") + int(value, 16).to_bytes(8, "little")
    for value in limits.values():
        query_bytes += value.to_bytes(8, "little")
    report = {
        "schema": "ariadne-minidump-report-v1",
        "identity": {"artifact_sha256": artifact, "snapshot_id": snapshot, "platform": "windows",
                     "query_id": digest(query_bytes)},
        "query": {"entries": [ENTRY], "seeds": [SITE], "exception_rip_seed": False},
        "input": {"prepare_limits": limits}, "analysis": {"phase": "done"},
        "analysis_backend": {
            "schema": "ariadne.analysis-backend/v1", "backend": "bap",
            "snapshot": snapshot, "query": digest(b"native captured query"),
            "family": "recovery", "profile": NATIVE.PROFILE, "build": copy.deepcopy(manifest),
        },
    }
    inspection = {
        "inputs": {"dump": {"sha256": artifact}},
        "query": {"entry_points": [ENTRY], "slice_seeds": [SITE],
                  "fault_instruction": SITE, "memory_access_index": 0},
    }
    return report, inspection, manifest


class CaptureFixture:
    """A complete record graph whose hashes bind real temporary file bytes."""

    def __init__(self, root, mode="partial"):
        self.root, self.mode = root, mode
        self.captures = root / "captures"
        self.build_dir, self.case = self.captures / "build", self.captures / mode
        self.inspection_path = root / "fresh" / mode / "inspection.json"
        self.build_dir.mkdir(parents=True)
        self.case.mkdir(parents=True)
        self.inspection_path.parent.mkdir(parents=True)
        self.inspector_sha = digest(b"current inspector source")
        self.producer_sources = {name: digest(("historical " + name).encode())
                                 for name in ("BUILD.gn", "crash_demo.cc", "fault.cc")}
        self.witness = {"process_id": 42, "dump_mode": mode, "fault_function_entry": ENTRY}
        self.write_json(self.case / "witness.json", self.witness)
        (self.case / "capture.dmp").write_bytes(b"MDMP synthetic provenance fixture")
        (self.case / "ariadne_crash_demo.exe").write_bytes(b"MZ synthetic executable fixture")
        identities = {
            key: {"sha256": ASSESS.sha(self.case / filename),
                  "size_bytes": (self.case / filename).stat().st_size}
            for key, filename in (("dump", "capture.dmp"), ("witness", "witness.json"),
                                  ("executable", "ariadne_crash_demo.exe"))
        }
        self.inputs = {
            "schema": "ariadne.crashpad-demo-build-inputs/v1", "crashpadRevision": "a" * 40,
            "demoSourceHashes": copy.deepcopy(self.producer_sources),
            "sourceHashes": {"examples/ariadne_demo/" + name: value
                             for name, value in self.producer_sources.items()},
        }
        self.build = {
            "schema": "ariadne.crashpad-demo-windows-build/v1", "passed": True,
            "sourcesStable": True, "architecture": "x64", "inputs": {},
            "crashpadRevision": "a" * 40,
            "binaryHashes": {"ariadne_crash_demo.exe": identities["executable"]["sha256"],
                             "crashpad_handler.exe": digest(b"historical handler")},
        }
        self.capture = {
            "schema": "ariadne.crashpad-demo-capture/v1", "captureCreated": True,
            "uploadsEnabled": False, "host": "native Windows", "mode": mode,
            "processId": 42, "crashpadRevision": "a" * 40,
            "handlerSha256": self.build["binaryHashes"]["crashpad_handler.exe"],
            "dump": {"sha256": identities["dump"]["sha256"], "bytes": identities["dump"]["size_bytes"]},
            "witnessSha256": identities["witness"]["sha256"],
            "executableSha256": identities["executable"]["sha256"],
        }
        self.historical = {
            "schema": "ariadne.crashpad-demo-capture-inspection/v1", "passed": True,
            "requested_dump_mode": mode, "process_id": 42, "inputs": identities,
            "query": {"entry_points": [ENTRY], "slice_seeds": [SITE],
                      "fault_instruction": SITE, "memory_access_index": 0},
            "local_source_files": {name: {"sha256": value}
                                   for name, value in self.producer_sources.items() if name != "BUILD.gn"},
        }
        self.inspection = copy.deepcopy(self.historical)
        self.inspection["local_source_files"]["inspect_capture.py"] = {"sha256": self.inspector_sha}
        self.inspection["local_source_files"]["crash_demo.cc"] = {"sha256": digest(b"current demo observation")}
        self.write_records()

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value, indent=2) + "\n")

    def write_records(self):
        """Seal parent hashes after a targeted semantic mutation."""
        self.write_json(self.build_dir / "build-inputs.json", self.inputs)
        self.build["inputs"]["inputsSha256"] = ASSESS.sha(self.build_dir / "build-inputs.json")
        self.write_json(self.build_dir / "build.json", self.build)
        self.capture["buildRecordSha256"] = ASSESS.sha(self.build_dir / "build.json")
        self.write_json(self.case / "capture.json", self.capture)
        self.write_json(self.case / "inspection.json", self.historical)
        self.write_json(self.inspection_path, self.inspection)

    def validate(self):
        return ASSESS.validate_capture_provenance(
            self.captures, self.mode, self.inspection_path, self.inspector_sha)


class SourceFixtureRecordTests(unittest.TestCase):
    def setUp(self):
        self.sources = {"src/lib.rs": digest(b"source"),
                        "tools/test_crashpad_assessment.py": digest(b"test")}
        self.tools = {name: digest(name.encode()) for name in NATIVE.TOOL_PATHS}
        native_evidence = {"passed": True, "defaultNativeVerified": True,
                           "analysisBackend": "bap", "analysisProfile": NATIVE.PROFILE}
        self.record = {
            "schema": "ariadne.i5a-acceptance/v2", "passed": True,
            "sourceFixtureAcceptancePassed": True, "sourcesStable": True,
            "toolsStable": True, "defaultNativeVerified": True,
            "analysisBackend": "bap", "analysisProfile": NATIVE.PROFILE,
            "sourceHashes": copy.deepcopy(self.sources), "tools": copy.deepcopy(self.tools),
            "gates": [{"gate": gate, "exitCode": 0} for gate in sorted(NATIVE.GATES)],
            "records": {name: copy.deepcopy(native_evidence)
                        for name in ("measurements", "equivalence")},
        }

    def validate(self):
        NATIVE.validate_source_fixture_record(self.record, self.sources, self.tools)

    def test_complete_native_v2_record_is_accepted(self):
        self.validate()

    def test_stale_or_incomplete_source_inventory_is_rejected(self):
        for operation in ("stale", "missing", "extra"):
            with self.subTest(operation=operation):
                original = copy.deepcopy(self.record["sourceHashes"])
                if operation == "stale":
                    self.record["sourceHashes"]["src/lib.rs"] = OTHER_SHA
                elif operation == "missing":
                    self.record["sourceHashes"].pop("tools/test_crashpad_assessment.py")
                else:
                    self.record["sourceHashes"]["retired-source.rs"] = OTHER_SHA
                with self.assertRaisesRegex(ValueError, "inventory"):
                    self.validate()
                self.record["sourceHashes"] = original

    def test_incomplete_tool_inventory_cannot_pass_by_matching_itself(self):
        missing = "target/bap-core-native/manifest.json"
        self.tools.pop(missing)
        self.record["tools"].pop(missing)
        with self.assertRaisesRegex(ValueError, "tool inventory"):
            self.validate()

    def test_changed_native_tool_is_rejected(self):
        self.record["tools"]["target/bap-core-native/ariadne-bap-core"] = OTHER_SHA
        with self.assertRaisesRegex(ValueError, "tool inventory"):
            self.validate()

    def test_old_schema_and_false_qualification_flags_are_rejected(self):
        for key, value in (("schema", "ariadne.i5a-acceptance/v1"),
                           ("analysisBackend", "rust"),
                           ("analysisProfile", "normalized-fixed-input/v1"),
                           *((key, False) for key in ("passed", "sourceFixtureAcceptancePassed",
                                                     "sourcesStable", "toolsStable", "defaultNativeVerified"))):
            with self.subTest(key=key):
                original = self.record[key]
                self.record[key] = value
                with self.assertRaises(ValueError):
                    self.validate()
                self.record[key] = original

    def test_missing_failed_or_duplicate_gate_is_rejected(self):
        for operation in ("missing", "failed", "duplicate", "boolean-exit"):
            with self.subTest(operation=operation):
                original = copy.deepcopy(self.record["gates"])
                if operation == "missing":
                    self.record["gates"].pop()
                elif operation == "duplicate":
                    self.record["gates"][0] = copy.deepcopy(self.record["gates"][1])
                else:
                    self.record["gates"][0]["exitCode"] = 1 if operation == "failed" else False
                with self.assertRaisesRegex(ValueError, "gates incomplete"):
                    self.validate()
                self.record["gates"] = original

    def test_missing_or_non_native_nested_evidence_is_rejected(self):
        for name in ("measurements", "equivalence"):
            for key, value in (("passed", False), ("defaultNativeVerified", False),
                               ("analysisBackend", "rust"), ("analysisProfile", "wrong")):
                with self.subTest(record=name, key=key):
                    original = copy.deepcopy(self.record["records"][name])
                    self.record["records"][name][key] = value
                    with self.assertRaisesRegex(ValueError, "native evidence missing"):
                        self.validate()
                    self.record["records"][name] = original
            original = self.record["records"].pop(name)
            with self.subTest(record=name, missing=True), self.assertRaises(ValueError):
                self.validate()
            self.record["records"][name] = original


class NativeReportTests(unittest.TestCase):
    def setUp(self):
        self.report, self.inspection, self.manifest = report_fixture()

    def assert_rejected_by_both(self, report):
        with self.assertRaises(ValueError):
            NATIVE.validate_backend_receipt(report, self.manifest)
        with self.assertRaises(ValueError):
            ASSESS.validate_cli_report(report, self.inspection, self.manifest)

    def test_complete_bound_native_report_is_accepted(self):
        receipt = NATIVE.validate_backend_receipt(self.report, self.manifest)
        self.assertNotEqual(receipt["query"], self.report["identity"]["query_id"])
        ASSESS.validate_cli_report(self.report, self.inspection, self.manifest)

    def test_missing_native_receipt_or_fields_is_rejected(self):
        report = copy.deepcopy(self.report)
        report.pop("analysis_backend")
        self.assert_rejected_by_both(report)
        for field in self.report["analysis_backend"]:
            with self.subTest(field=field):
                report = copy.deepcopy(self.report)
                report["analysis_backend"].pop(field)
                self.assert_rejected_by_both(report)

    def test_wrong_backend_build_profile_snapshot_or_query_is_rejected(self):
        for key, value in (("backend", "rust"), ("profile", "normalized-fixed-input/v1"),
                           ("family", "stateflow"), ("snapshot", "another-snapshot"),
                           ("query", "not-a-digest"), ("build", {})):
            with self.subTest(key=key):
                report = copy.deepcopy(self.report)
                report["analysis_backend"][key] = value
                self.assert_rejected_by_both(report)
        report = copy.deepcopy(self.report)
        report["analysis_backend"]["build"]["helper_sha256"] = OTHER_SHA
        self.assert_rejected_by_both(report)

    def test_public_query_identity_and_preparation_limits_are_bound(self):
        for mutate in (
                lambda report: report["identity"].update(query_id=OTHER_SHA),
                lambda report: report["query"].update(entries=["0x0000000140001001"]),
                lambda report: report["input"]["prepare_limits"].update(max_starts=4095),
                lambda report: report["analysis"].update(phase="recovering")):
            report = copy.deepcopy(self.report)
            mutate(report)
            self.assert_rejected_by_both(report)

    def test_inspected_artifact_entry_and_seed_are_required(self):
        for mutate in (
                lambda inspection: inspection["inputs"]["dump"].update(sha256=OTHER_SHA),
                lambda inspection: inspection["query"].update(entry_points=["0x140001001"]),
                lambda inspection: inspection["query"].update(slice_seeds=["0x140001005"])):
            inspection = copy.deepcopy(self.inspection)
            mutate(inspection)
            # A complete native receipt cannot substitute for the independent
            # capture's artifact and explicit local query.
            NATIVE.validate_backend_receipt(self.report, self.manifest)
            with self.assertRaises(ValueError):
                ASSESS.validate_cli_report(self.report, inspection, self.manifest)
        for field, value in (("schema", "other"), ("schema", None)):
            report = copy.deepcopy(self.report)
            if value is None:
                report.pop(field)
            else:
                report[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                ASSESS.validate_cli_report(report, self.inspection, self.manifest)


class CaptureProvenanceTests(unittest.TestCase):
    def test_complete_partial_and_full_record_graphs_are_accepted(self):
        for mode in ("partial", "full"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                fixture = CaptureFixture(Path(directory), mode)
                inspection, provenance, hashes = fixture.validate()
                self.assertEqual(inspection, fixture.inspection)
                self.assertEqual(provenance["historicalProducerSourceHashes"], fixture.producer_sources)
                self.assertEqual(provenance["inputHashes"]["dump"], fixture.capture["dump"]["sha256"])
                self.assertEqual(len(hashes), 8)
                self.assertEqual(hashes, {path: ASSESS.sha(path) for path in hashes})

    def test_current_demo_source_observation_can_differ_from_historical_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = CaptureFixture(Path(directory))
            current = fixture.inspection["local_source_files"]["crash_demo.cc"]["sha256"]
            historical = fixture.producer_sources["crash_demo.cc"]
            self.assertNotEqual(current, historical)
            _, provenance, _ = fixture.validate()
            self.assertEqual(provenance["historicalProducerSourceHashes"]["crash_demo.cc"], historical)
            self.assertEqual(provenance["inspectionLocalSourceObservations"]["crash_demo.cc"]["sha256"], current)

    def test_changed_raw_dump_witness_or_executable_is_rejected(self):
        for filename in ("capture.dmp", "witness.json", "ariadne_crash_demo.exe"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                fixture = CaptureFixture(Path(directory))
                with (fixture.case / filename).open("ab") as stream:
                    stream.write(b" changed")
                with self.assertRaisesRegex(ValueError, "inspection input changed"):
                    fixture.validate()

    def test_changed_build_or_inputs_record_bytes_are_rejected(self):
        for filename, message in (("build.json", "capture/build record changed"),
                                  ("build-inputs.json", "historical build inputs changed")):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                fixture = CaptureFixture(Path(directory))
                with (fixture.build_dir / filename).open("a") as stream:
                    stream.write(" ")  # Same parsed JSON still has a different producer identity.
                with self.assertRaisesRegex(ValueError, message):
                    fixture.validate()

    def test_capture_and_inspection_input_claims_are_independently_checked(self):
        mutations = (
            ("capture dump", lambda f: f.capture["dump"].update(sha256=OTHER_SHA)),
            ("capture dump size", lambda f: f.capture["dump"].update(bytes=0)),
            ("capture witness", lambda f: f.capture.update(witnessSha256=OTHER_SHA)),
            ("capture executable", lambda f: f.capture.update(executableSha256=OTHER_SHA)),
            ("current dump", lambda f: f.inspection["inputs"]["dump"].update(sha256=OTHER_SHA)),
            ("historical witness", lambda f: f.historical["inputs"]["witness"].update(sha256=OTHER_SHA)),
            ("current executable size", lambda f: f.inspection["inputs"]["executable"].update(size_bytes=0)),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                fixture = CaptureFixture(Path(directory))
                mutate(fixture)
                fixture.write_records()
                with self.assertRaisesRegex(ValueError, "input changed|dump size changed"):
                    fixture.validate()

    def test_build_binaries_handler_and_revision_mismatches_are_rejected(self):
        mutations = (
            ("handler", lambda f: f.capture.update(handlerSha256=OTHER_SHA), "handler mismatch"),
            ("missing handler", lambda f: f.build["binaryHashes"].pop("crashpad_handler.exe"), "handler mismatch"),
            ("executable", lambda f: f.build["binaryHashes"].update({"ariadne_crash_demo.exe": OTHER_SHA}), "executable mismatch"),
            ("capture revision", lambda f: f.capture.update(crashpadRevision="b" * 40), "revision mismatch"),
            ("inputs revision", lambda f: f.inputs.update(crashpadRevision="b" * 40), "revision mismatch"),
        )
        for name, mutate, message in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                fixture = CaptureFixture(Path(directory))
                mutate(fixture)
                fixture.write_records()
                with self.assertRaisesRegex(ValueError, message):
                    fixture.validate()

    def test_historical_producer_source_inventory_is_required(self):
        mutations = (
            ("missing source", lambda f: f.inputs["demoSourceHashes"].pop("fault.cc")),
            ("source binding", lambda f: f.inputs["sourceHashes"].update({"examples/ariadne_demo/fault.cc": OTHER_SHA})),
            ("historical source", lambda f: f.historical["local_source_files"]["crash_demo.cc"].update(sha256=OTHER_SHA)),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                fixture = CaptureFixture(Path(directory))
                mutate(fixture)
                fixture.write_records()
                with self.assertRaisesRegex(ValueError, "producer source"):
                    fixture.validate()

    def test_capture_process_query_mode_and_inspector_binding_are_required(self):
        mutations = (
            ("process", lambda f: f.capture.update(processId=43)),
            ("mode", lambda f: f.capture.update(mode="full")),
            ("query", lambda f: f.inspection["query"].update(slice_seeds=[ENTRY])),
            ("inspector", lambda f: f.inspection["local_source_files"]["inspect_capture.py"].update(sha256=OTHER_SHA)),
            ("uploads", lambda f: f.capture.update(uploadsEnabled=True)),
            ("build", lambda f: f.build.update(passed=False)),
            ("inspection", lambda f: f.inspection.update(passed=False)),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                fixture = CaptureFixture(Path(directory))
                mutate(fixture)
                fixture.write_records()
                with self.assertRaises(ValueError):
                    fixture.validate()


class AssessmentBindingTests(unittest.TestCase):
    def setUp(self):
        self.report, self.inspection, _ = report_fixture()
        self.result = {
            "schema": "ariadne.zero-address-assessment/v1",
            "profile": "windows-amd64-av-scalar-mov-v1", "conclusion": "consistent_with_evidence",
            "gaps": [], "truncated": False, "evaluated_address": {"value": "0x0000000000000000"},
            "identity": copy.deepcopy(self.report["identity"]),
            "question": {"site": SITE, "memory_access": 0},
        }

    def validate(self):
        ASSESS.validate_assessment(self.result, self.report, self.inspection)

    def test_complete_assessment_matches_independent_oracle(self):
        self.validate()

    def test_wrong_or_missing_snapshot_artifact_and_query_binding_is_rejected(self):
        for key in ("snapshot_id", "artifact_sha256", "query_id"):
            for missing in (False, True):
                with self.subTest(key=key, missing=missing):
                    original = copy.deepcopy(self.result["identity"])
                    if missing:
                        self.result["identity"].pop(key)
                    else:
                        self.result["identity"][key] = OTHER_SHA
                    with self.assertRaisesRegex(ValueError, "null-write oracle"):
                        self.validate()
                    self.result["identity"] = original

    def test_wrong_conclusion_question_or_incomplete_result_is_rejected(self):
        for key, value in (("schema", "other"), ("profile", "other"), ("conclusion", "unknown"),
                           ("gaps", ["missing context"]), ("truncated", True),
                           ("evaluated_address", {"value": "0x0000000000000001"}),
                           ("question", {"site": ENTRY, "memory_access": 0}),
                           ("question", {"site": SITE, "memory_access": 1})):
            with self.subTest(key=key, value=value):
                original = copy.deepcopy(self.result[key])
                self.result[key] = value
                with self.assertRaises(ValueError):
                    self.validate()
                self.result[key] = original


class PerformanceCriteriaTests(unittest.TestCase):
    def setUp(self):
        self.contract = performance_contract()

    def test_frozen_contract_and_budget_boundaries_are_accepted(self):
        ASSESS.validate_performance_contract(self.contract)
        result = ASSESS.qualify_samples([10] * 5, [1500] * 5, self.contract)
        self.assertEqual(result, {"phaseMedianMs": 10, "assessmentCliMedianMs": 1500,
                                  "phaseBudgetMet": True, "cliBudgetMet": True, "passed": True})

    def test_changed_or_missing_sampling_and_budget_criteria_are_rejected(self):
        for key, values in (("warmups", (0, 2, True, 1.0)), ("repeats", (1, 4, 6, 5.0)),
                            ("phaseMedianBudgetMs", (11, None, 10.0)),
                            ("cliMedianBudgetMs", (1501, None, 1500.0))):
            for value in (*values, "missing"):
                with self.subTest(key=key, value=value):
                    contract = copy.deepcopy(self.contract)
                    if value == "missing":
                        contract.pop(key)
                    else:
                        contract[key] = value
                    with self.assertRaisesRegex(ValueError, "criteria changed"):
                        ASSESS.validate_performance_contract(contract)

    def test_overbudget_phases_or_cli_cannot_qualify(self):
        for phase, cli, phase_met, cli_met in ((10.01, 1499, False, True),
                                               (9, 1500.01, True, False),
                                               (10.01, 1500.01, False, False)):
            with self.subTest(phase=phase, cli=cli):
                result = ASSESS.qualify_samples([phase] * 5, [cli] * 5, self.contract)
                self.assertFalse(result["passed"])
                self.assertEqual(result["phaseBudgetMet"], phase_met)
                self.assertEqual(result["cliBudgetMet"], cli_met)

    def test_budget_uses_all_five_measured_samples_median(self):
        result = ASSESS.qualify_samples([2, 30, 4, 10, 100], [1400, 2000, 1499, 3, 1500], self.contract)
        self.assertEqual(result["phaseMedianMs"], 10)
        self.assertEqual(result["assessmentCliMedianMs"], 1499)
        self.assertTrue(result["passed"])

    def test_missing_extra_nonfinite_negative_and_nonnumeric_samples_are_rejected(self):
        invalid_sets = ([1] * 4, [1] * 6, [],
                        *([1, 2, invalid, 4, 5] for invalid in
                          (float("nan"), float("inf"), -float("inf"), -1, True, "3", None)))
        for samples in invalid_sets:
            for phase_side in (False, True):
                with self.subTest(samples=samples, phase_side=phase_side):
                    phase, cli = (samples, [100] * 5) if phase_side else ([1] * 5, samples)
                    with self.assertRaisesRegex(ValueError, "invalid measured samples"):
                        ASSESS.qualify_samples(phase, cli, self.contract)


if __name__ == "__main__":
    unittest.main()
