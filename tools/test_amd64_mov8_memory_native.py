"""Memory-native contract controls. Fake processes remain confined to unit tests."""
import copy
from pathlib import Path
import tempfile
import unittest

import amd64_domains as domains
import check_amd64_mov8_memory_native as native
import check_amd64_mov8_native as register
from test_amd64_mov8_native import config, identity, process


def fixture_runner(calls, damage=None):
    def run(command, **kwargs):
        calls.append(command)
        name = command[6]
        marker = next(marker for _, selected, marker in native.TESTS if selected == name)
        artifact = Path(kwargs["env"]["CARGO_TARGET_DIR"]) / "release/deps/memory-unit-artifact"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"Unit fixture only; no actual native observations")
        result = process(name, marker, artifact=artifact)
        if damage:
            damage(result, name)
        return result
    return run


class MemoryNativeControls(unittest.TestCase):
    def setUp(self):
        self.document = domains.read(native.INPUT / "legal-domain.json")
        self.bindings = domains.read(native.INPUT / "profile-bindings.json")
        self.points = domains.enumerate_domain(self.document)

    def test_exact_finite_domain_and_existing_refused_half(self):
        result = native.validate_domain(self.document, self.points, self.bindings["partitions"])
        self.assertEqual((result["points"], result["supportedPoints"], result["refusedPoints"]), (5760, 2880, 2880))
        self.assertFalse(result["sourceComplete"])

    def test_omissions_duplicates_substitutions_or_address32_admission_fail(self):
        for attack in ("omit", "duplicate", "substitute", "admit32", "drop-partition", "complete-source"):
            points, partitions, document = copy.deepcopy((self.points, self.bindings["partitions"], self.document))
            if attack == "omit":
                points.pop()
            elif attack == "duplicate":
                points[-1] = points[0]
            elif attack == "substitute":
                points[0]["bytes"] = "90"
            elif attack == "admit32":
                partitions[0]["disposition"] = "S"
            elif attack == "drop-partition":
                partitions.pop()
            else:
                document["scope"]["sourceComplete"] = True
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                native.validate_domain(document, points, partitions)

    def test_closure_owns_current_memory_observer_and_checker(self):
        closure = native.source_closure()
        for path in ("tools/check_amd64_mov8_memory_native.py", "tools/test_amd64_mov8_memory_native.py",
                     "tests/bap/mov8_memory_native_consumer.rs", "tests/bap/mov8_native_consumer.rs",
                     "tools/check_amd64_mov8_native.py", "tools/amd64_memory_bindings.py",
                     "native/bap-core/capture.ml", "Cargo.toml", "Cargo.lock"):
            self.assertIn(path, closure)

    def test_seven_exact_named_gates_share_one_stable_executed_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            result = native.qualify(config(directory), runner=fixture_runner(calls), inspect=lambda _: identity())
            self.assertTrue(result["nativeConsumerValidated"])
            self.assertTrue(result["sourcesStable"] and result["testArtifactStable"])
            self.assertEqual(len(calls), 7)
            self.assertEqual([command[6] for command in calls], [name for _, name, _ in native.TESTS])
            self.assertEqual((result["nativeCaptureInstances"], result["nativeRefusedInstances"], result["nativeAnalysisBatches"]),
                             (5760, 5760, 180))
            self.assertEqual(result["registerRegressionInstances"], 1280)
            self.assertFalse(result["address32ProducerQualified"] or result["fullAmd64Coverage"])
            self.assertEqual(result["schema"], native.SCHEMA)

    def test_missing_wrong_duplicate_metrics_and_skipped_tests_fail(self):
        for attack in ("missing", "wrong-count", "duplicate", "ignored", "partial-summary", "failed-register"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as directory:
                def damage(result, name):
                    marker = next(marker for _, selected, marker in native.TESTS if selected == name)
                    if "native_memory_mov8_preserves" in name:
                        if attack == "missing":
                            result.stdout = result.stdout.replace(marker, "")
                        elif attack == "wrong-count":
                            result.stdout = result.stdout.replace("instances=5760", "instances=5759")
                        elif attack == "duplicate":
                            result.stderr += marker + "\n"
                        elif attack == "ignored":
                            result.stdout = result.stdout.replace(" ... ok", " ... ignored")
                        elif attack == "partial-summary":
                            result.stdout = result.stdout.split("test result:")[0]
                    if attack == "failed-register" and name == register.TESTS[0][1]:
                        result.returncode = 1
                result = native.qualify(config(directory), runner=fixture_runner([], damage), inspect=lambda _: identity())
                self.assertFalse(result["nativeConsumerValidated"])
                self.assertEqual(result["nativeCaptureInstances"], 0)
                self.assertEqual(result["nativeRefusedInstances"], 0)
                self.assertFalse(result["registerRegressionValidated"])

    def test_source_drift_cannot_preserve_native_credit(self):
        with tempfile.TemporaryDirectory() as directory:
            count = 0
            def inspect(_):
                nonlocal count
                count += 1
                result = identity()
                if count > 1:
                    result["sourceHashes"]["memory-observer.rs"] = "changed"
                return result
            result = native.qualify(config(directory), runner=fixture_runner([]), inspect=inspect)
            self.assertFalse(result["nativeConsumerValidated"])
            self.assertIn("changed during execution", result["error"])

    def test_empty_selected_plan_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "named tests"):
            register.qualify(config(directory), tests=(), inspect=lambda _: identity())


if __name__ == "__main__":
    unittest.main()
