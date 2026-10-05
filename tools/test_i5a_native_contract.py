"""Negative acceptance controls for native I5a receipts, timings and inventories."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import check_i5a
import i5a_native_contract as contract
from compare_i5a_cli import without_verified_receipt


class NativeContractTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"schema": "ariadne.bap-core-build/v1", "helper_sha256": "a" * 64,
                         "lock_sha256": "b" * 64, "handshake": {"abi": 2}}
        self.report = {"identity": {"artifact_sha256": "c" * 64,
                                   "snapshot_id": "minidump-captured-amd64-v1:" + "c" * 64},
                       "query": {"entries": ["0x0000000000401000"], "seeds": ["0x0000000000401006"]},
                       "input": {"prepare_limits": {"max_starts": 4096, "max_candidates": 8192,
                                                    "max_prefix_bytes": 61440,
                                                    "max_decoder_batches": 4096, "batch_size": 128}},
                       "analysis": {"phase": "done", "decoded": ["0x0000000000401006"]}}
        self.report["identity"]["query_id"] = contract.report_query_digest(self.report)
        self.report["analysis_backend"] = {
            "schema": "ariadne.analysis-backend/v1", "backend": "bap", "family": "recovery",
            "profile": contract.PROFILE, "snapshot": self.report["identity"]["snapshot_id"],
            "query": "d" * 64, "build": self.manifest,
        }
        self.performance = {"warmups": 1, "repeats": 5, "phaseMedianBudgetMs": 10, "cliMedianBudgetMs": 1500}
        self.rows = [{
            "artifact_sha256": self.report["identity"]["artifact_sha256"], "run": str(n),
            "binding_ns": "100", "assessment_ns": "200", "render_ns": "300", "total_ns": "600",
            "evidence": "3", "claims": "4", "conclusion": "ConsistentWithEvidence",
            "output_sha256": "e" * 64, "analysis_backend": "bap", "analysis_profile": contract.PROFILE,
            "analysis_family": "recovery", "snapshot_id": self.report["identity"]["snapshot_id"],
            "query_id": self.report["identity"]["query_id"], "backend_query": "d" * 64,
            "helper_sha256": "a" * 64, "manifest_sha256": contract.manifest_digest(self.manifest),
            "entry": self.report["query"]["entries"][0], "site": self.report["query"]["seeds"][0],
            "memory_access": "0",
        } for n in range(6)]
        self.sources = {"src/bin/i5a.rs": "0" * 64, "tools/i5a_native_contract.py": "1" * 64}
        self.tools = dict.fromkeys(contract.TOOL_PATHS, "2" * 64)
        self.acceptance = {
            "schema": "ariadne.i5a-acceptance/v2", "passed": True, "sourceFixtureAcceptancePassed": True,
            "sourcesStable": True, "toolsStable": True, "defaultNativeVerified": True,
            "analysisBackend": "bap", "analysisProfile": contract.PROFILE,
            "sourceHashes": self.sources, "tools": self.tools, "helperManifest": self.manifest,
            "gates": [{"gate": name, "exitCode": 0} for name in sorted(contract.GATES)],
            "records": {name: {"passed": True, "defaultNativeVerified": True, "analysisBackend": "bap",
                               "analysisProfile": contract.PROFILE} for name in ["measurements", "equivalence"]},
        }

    def test_valid_native_receipt_phase_and_acceptance(self):
        self.assertEqual(contract.validate_backend_receipt(self.report, self.manifest), self.report["analysis_backend"])
        self.assertEqual(contract.validate_phase_rows(self.rows, self.report, self.manifest, self.performance,
                                                      conclusion="ConsistentWithEvidence", output_sha256="e" * 64), [0.0006] * 5)
        contract.validate_source_fixture_record(self.acceptance, self.sources, self.tools)
        for row in self.rows:
            row["conclusion"] = "RefutedUnderPremises"
        contract.validate_phase_rows(self.rows, self.report, self.manifest, self.performance,
                                     conclusion="RefutedUnderPremises")

    def test_fixture_cannot_cross_dependency_snapshots(self):
        environment = {"manifestSha256": "f" * 64, "readOnly": True}
        self.acceptance["qualificationEnvironment"] = environment
        contract.validate_source_fixture_record(
            self.acceptance, self.sources, self.tools, qualification_environment=environment)
        for expected in (None, {**environment, "manifestSha256": "0" * 64}):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                contract.validate_source_fixture_record(
                    self.acceptance, self.sources, self.tools, qualification_environment=expected)

    def test_missing_foreign_and_unknown_backend_receipts_fail(self):
        broken = copy.deepcopy(self.report)
        del broken["analysis_backend"]
        with self.assertRaises(ValueError):
            contract.validate_backend_receipt(broken, self.manifest)
        for field, value in [("backend", "rust"), ("profile", "normalized-fixed-input/v1"),
                             ("family", "stateflow"), ("query", "not-a-digest"),
                             ("schema", "ariadne.analysis-backend/v0"), ("unvalidated", True)]:
            with self.subTest(field=field):
                broken = copy.deepcopy(self.report)
                broken["analysis_backend"][field] = value
                with self.assertRaises(ValueError):
                    contract.validate_backend_receipt(broken, self.manifest)

    def test_snapshot_artifact_build_and_completion_substitution_fail(self):
        for path, value in [(('analysis_backend', 'snapshot'), 'other'),
                            (('identity', 'artifact_sha256'), 'f' * 64),
                            (('analysis_backend', 'build', 'helper_sha256'), 'f' * 64),
                            (('analysis_backend', 'build', 'handshake', 'abi'), 1),
                            (('analysis_backend', 'build', 'handshake', 'abi'), 2.0),
                            (('analysis', 'phase'), 'dataflow')]:
            with self.subTest(path=path):
                broken = copy.deepcopy(self.report)
                target = broken
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaises(ValueError):
                    contract.validate_backend_receipt(broken, self.manifest)

    def test_report_query_or_limit_substitution_fails(self):
        for field, value in [("entries", ["0x0000000000401001"]),
                             ("seeds", ["0x0000000000401007"]),
                             ("entries", ["0x401000"]),
                             ("entries", ["0x0000000000401000"] * 2)]:
            with self.subTest(field=field, value=value):
                broken = copy.deepcopy(self.report)
                broken["query"][field] = value
                with self.assertRaises(ValueError):
                    contract.validate_backend_receipt(broken, self.manifest)
        broken = copy.deepcopy(self.report)
        broken["input"]["prepare_limits"]["max_starts"] += 1
        with self.assertRaises(ValueError):
            contract.validate_backend_receipt(broken, self.manifest)

    def test_phase_bindings_reject_other_backend_query_build_or_question(self):
        for field in ["artifact_sha256", "analysis_backend", "analysis_profile", "analysis_family",
                      "snapshot_id", "query_id", "backend_query", "helper_sha256", "manifest_sha256",
                      "entry", "site", "memory_access"]:
            with self.subTest(field=field):
                broken = copy.deepcopy(self.rows)
                broken[3][field] = "different"
                with self.assertRaises(ValueError):
                    contract.validate_phase_rows(broken, self.report, self.manifest, self.performance)

    def test_missing_reordered_or_malformed_phase_samples_fail(self):
        with self.assertRaises(ValueError):
            contract.validate_phase_rows(self.rows[:-1], self.report, self.manifest, self.performance)
        for field, value in [("run", "2"), ("total_ns", "601"), ("binding_ns", "-1"),
                             ("render_ns", "NaN"), ("claims", "1.5"), ("conclusion", "RootCause"),
                             ("output_sha256", "f" * 64)]:
            with self.subTest(field=field):
                broken = copy.deepcopy(self.rows)
                broken[1][field] = value
                with self.assertRaises(ValueError):
                    contract.validate_phase_rows(broken, self.report, self.manifest, self.performance)
        with self.assertRaises(ValueError):
            contract.validate_phase_rows(self.rows, self.report, self.manifest, self.performance,
                                         output_sha256="f" * 64)
        with self.assertRaises(ValueError):
            contract.validate_phase_rows(self.rows, self.report, self.manifest, self.performance,
                                         conclusion="Unknown")

    def test_frozen_performance_contract_and_warmup_exclusion(self):
        self.rows[0].update(binding_ns="100000000", total_ns="100000500")
        self.assertEqual(contract.validate_phase_rows(self.rows, self.report, self.manifest, self.performance), [0.0006] * 5)
        for field in self.performance:
            broken = dict(self.performance)
            broken[field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                contract.validate_phase_rows(self.rows, self.report, self.manifest, broken)

    def test_retained_source_and_tool_inventory_must_be_exact(self):
        for field in ["sourceHashes", "tools"]:
            for change in ["delete", "add", "modify"]:
                with self.subTest(field=field, change=change):
                    broken = copy.deepcopy(self.acceptance)
                    key = next(iter(broken[field]))
                    if change == "delete":
                        del broken[field][key]
                    elif change == "add":
                        broken[field]["unexpected"] = "f" * 64
                    else:
                        broken[field][key] = "f" * 64
                    with self.assertRaises(ValueError):
                        contract.validate_source_fixture_record(broken, self.sources, self.tools)

    def test_legacy_partial_and_false_acceptance_cannot_qualify(self):
        for key, value in [("schema", "ariadne.i5a-acceptance/v1"), ("analysisBackend", "rust"),
                           ("analysisProfile", "normalized-fixed-input/v1"), ("sourcesStable", False),
                           ("toolsStable", False), ("defaultNativeVerified", False),
                           ("sourceFixtureAcceptancePassed", False), ("passed", False)]:
            broken = copy.deepcopy(self.acceptance)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                contract.validate_source_fixture_record(broken, self.sources, self.tools)
        for target in ["gates", "records"]:
            broken = copy.deepcopy(self.acceptance)
            broken[target].pop() if target == "gates" else broken[target].pop("measurements")
            with self.subTest(target=target), self.assertRaises(ValueError):
                contract.validate_source_fixture_record(broken, self.sources, self.tools)

    def test_normalization_removes_only_verified_receipt(self):
        receipt = json.dumps(self.report["analysis_backend"])
        text, dot = "all original text\n", "digraph original {}\n"
        native_text = text + "analysis backend: " + receipt + "\n"
        native_dot = "// analysis backend: " + receipt + "\n" + dot
        normalized = without_verified_receipt(self.report, native_text, native_dot, self.manifest)
        self.assertEqual(normalized[1:], (text, dot))
        self.assertEqual(set(normalized[0]), set(self.report) - {"analysis_backend"})
        for changed_text, changed_dot in [(native_text + "extra\n", native_dot),
                                          (native_text + "analysis backend: " + receipt + "\n", native_dot),
                                          (native_text, native_dot.replace('"backend": "bap"', '"backend": "rust"')),
                                          (native_text, "// missing receipt\n" + dot)]:
            with self.subTest(text=changed_text, dot=changed_dot), self.assertRaises(ValueError):
                without_verified_receipt(self.report, changed_text, changed_dot, self.manifest)
        with self.assertRaises(ValueError):
            contract.strict_json('{"analysis_backend":{},"analysis_backend":{}}')
        with self.assertRaises(ValueError):
            contract.strict_json('{"value":NaN}')

    def test_retained_producer_inventory_rejects_omitted_new_sources(self):
        record = {"passed": True, "sourcesStable": True, "sourceHashes": {"old": "a" * 64},
                  "schema": "ariadne.i5a-mutations/v1", "observersUnchanged": True}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            path.write_text(json.dumps(record))
            producer = SimpleNamespace(sources=lambda: {**record["sourceHashes"], "new": "b" * 64})
            with patch.object(check_i5a.importlib, "import_module", return_value=producer):
                with self.assertRaises(RuntimeError):
                    check_i5a.retained(path, "mutations")

    def test_native_manifest_checks_source_helper_and_sdk_linkage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = root / "target/bap-core-native"
            source = root / "native/bap-core"
            core.mkdir(parents=True)
            source.mkdir(parents=True)
            sdk = root / "target/bap-core-sdk/sdk-manifest.json"
            sdk.parent.mkdir(parents=True)
            sdk.write_text('{"sdk":"pinned"}')
            lock = source / "sdk.lock.json"
            lock.write_text('{"bapSourceRevision":"revision"}')
            helper = core / "ariadne-bap-core"
            helper.write_bytes(b"qualified helper")
            names = ["recovery.ml", "stateflow.ml", "capture.ml", "project_state.ml", "main.ml"]
            for name in names + ["sdk_smoke.ml"]:
                (source / name).write_text(name)
            manifest = {"schema": "ariadne.bap-core-build/v1", "helper_sha256": contract.sha(helper),
                        "lock_sha256": contract.sha(lock), "handshake": {
                            "schema": "ariadne.bap-core-ready/v1", "abi": 2, "families": ["recovery", "stateflow"],
                            "profiles": ["normalized-fixed-input/v1", contract.PROFILE], "bap_revision": "revision",
                            "sdk_manifest_sha256": contract.sha(sdk),
                            "source_hashes": {name: contract.sha(source / name) for name in names}}}
            (core / "manifest.json").write_text(json.dumps(manifest))
            with patch.object(contract, "ROOT", root), patch.object(contract, "CORE", core):
                self.assertEqual(contract.native_manifest(), manifest)
                for path in [helper, lock, sdk, source / "capture.ml"]:
                    original = path.read_bytes()
                    path.write_bytes(original + b"changed")
                    try:
                        with self.subTest(path=path), self.assertRaises(ValueError):
                            contract.native_manifest()
                    finally:
                        path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
