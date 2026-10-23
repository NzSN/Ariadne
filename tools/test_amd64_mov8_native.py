"""Protocol and lifecycle controls; fake processes are confined to this unit layer."""
import copy
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import amd64_domains
import check_amd64_mov8_native as native


def config(directory):
    directory = Path(directory)
    return SimpleNamespace(output=directory / "qualification", helper=directory / "bap", runtime=directory / "runtime",
        reference=directory / "llvm", reference_library=directory / "lib/libLLVM.so", core=directory / "core", timeout=30)


def identity():
    return dict(sourceHashes={"observer.rs": "a" * 64}, domain=dict(points=640),
                toolchain=dict(cargo=dict(path="cargo"), rustc=dict(path="rustc")),
                qualificationEnvironment=dict(readOnly=True, manifestSha256="b" * 64))


def process(name, marker=None, *, returncode=0, artifact=None):
    stdout = f"running 1 test\ntest {name} ... ok\n"
    if marker:
        stdout += "\nsuccesses:\n" + marker + "\n"
    stdout += "\ntest result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 500 filtered out; finished in 0.01s\n"
    stderr = f"Running unittests src/lib.rs ({artifact})\n" if artifact else ""
    return subprocess.CompletedProcess(["unit-fake-process"], returncode, stdout, stderr)


def runner(commands, damage=None):
    def run(command, **kwargs):
        commands.append((command, kwargs))
        name = command[6]
        marker = next(marker for _, selected, marker in native.TESTS if selected == name)
        artifact = Path(kwargs["env"]["CARGO_TARGET_DIR"]) / "release/deps/unit-test-artifact"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"Unit fixture only: not a Rust/native qualification artifact")
        result = process(name, marker, artifact=artifact)
        if damage:
            damage(result)
        return result
    return run


class Mov8NativeControls(unittest.TestCase):
    def test_actual_register_domain_is_exactly_the_observer_domain(self):
        domain = native.read(native.INPUT / "legal-domain.json")
        points = list(amd64_domains.enumerate_domain(domain))
        classified = {native.bindings_tool.point_key(point): "S" for point in points}
        self.assertEqual(native.validate_domain(points, classified)["points"], 640)

    def test_domain_omissions_duplicates_other_bytes_and_unsupported_partitions_fail(self):
        original = list(amd64_domains.enumerate_domain(native.read(native.INPUT / "legal-domain.json")))
        for attack in ("omit", "duplicate", "other-byte", "unsupported"):
            points = copy.deepcopy(original)
            if attack == "omit":
                points.pop()
            elif attack == "duplicate":
                points[-1] = points[0]
            elif attack == "other-byte":
                points[0]["bytes"] = "6790"
            classified = {native.bindings_tool.point_key(point): "S" for point in points}
            if attack == "unsupported":
                classified[next(iter(classified))] = "U"
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                native.validate_domain(points, classified)

    def test_current_closure_contains_native_observers_hook_and_gate(self):
        closure = native.source_closure()
        for name in ("tests/bap/mov8_native_consumer.rs", "tests/bap/mov8_address_size_guard.rs",
                     "src/bap/projection.rs", "tests/input/common/mod.rs", "tools/check_amd64_mov8_native.py",
                     "tools/with_mirrorrust_snapshot.py", "native/bap-core/capture.ml",
                     "Cargo.toml", "Cargo.lock", "tools/rust_layout.py"):
            self.assertIn(name, closure)

    def test_exact_named_test_and_required_native_counts_pass(self):
        for _, name, marker in native.TESTS:
            self.assertEqual(native.validate_test_process(process(name, marker), name, marker)["passed"], 1)

    def test_zero_tests_wrong_name_ignored_duplicate_or_failed_test_cannot_pass(self):
        _, name, marker = native.TESTS[1]
        for attack in ("zero", "name", "ignored", "duplicate", "failed-summary", "nonzero"):
            result = process(name, marker)
            if attack == "zero":
                result.stdout = result.stdout.replace("running 1 test", "running 0 tests")
            elif attack == "name":
                result.stdout = result.stdout.replace(name, "unrelated_test")
            elif attack == "ignored":
                result.stdout = result.stdout.replace(" ... ok", " ... ignored")
            elif attack == "duplicate":
                result.stdout += f"test {name} ... ok\n"
            elif attack == "failed-summary":
                result.stdout = result.stdout.replace("0 failed", "1 failed")
            else:
                result.returncode = 1
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                native.validate_test_process(result, name, marker)

    def test_missing_changed_or_duplicate_native_markers_cannot_pass(self):
        _, name, marker = native.TESTS[1]
        for attack in ("missing", "changed", "duplicate", "conflicting"):
            result = process(name, marker)
            if attack == "missing":
                result.stdout = result.stdout.replace(marker, "")
            elif attack == "changed":
                result.stdout = result.stdout.replace("instances=1280", "instances=1279")
            elif attack == "duplicate":
                result.stderr = marker + "\n"
            else:
                result.stderr = "MOV8_NATIVE_CONSUMER instances=0\n"
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                native.validate_test_process(result, name, marker)

    def test_partial_output_without_final_summary_is_not_a_pass(self):
        _, name, marker = native.TESTS[1]
        result = process(name, marker)
        result.stdout = result.stdout.split("test result:")[0]
        with self.assertRaisesRegex(ValueError, "summary"):
            native.validate_test_process(result, name, marker)

    def test_artifact_must_be_the_single_executed_file_in_isolated_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.mkdir()
            artifact = target / "test"
            artifact.write_bytes(b"unit fixture")
            result = process("test", artifact=artifact)
            self.assertEqual(native.test_artifact(result, target)["sha256"], native.sha(artifact))
            result.stderr += result.stderr
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                native.test_artifact(result, target)
            outside = root / "outside"
            outside.write_bytes(artifact.read_bytes())
            with self.assertRaisesRegex(ValueError, "outside isolated"):
                native.test_artifact(process("test", artifact=outside), target)
            artifact.unlink()
            artifact.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "outside isolated"):
                native.test_artifact(process("test", artifact=artifact), target)

    def test_environment_selects_exact_helpers_and_clears_ambient_runner_overrides(self):
        with tempfile.TemporaryDirectory() as temporary:
            selected = config(temporary)
            with patch.dict(os.environ, dict(RUSTC_WRAPPER="fake", RUSTFLAGS="--cfg stale",
                    CARGO_BUILD_TARGET="wrong", CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUNNER="skip",
                    RUST_TEST_NOCAPTURE="1", LD_PRELOAD="foreign.so")):
                env = native.execution_environment(selected, selected.output / "cargo", "/exact/rustc")
            for name in ("RUSTC_WRAPPER", "RUSTFLAGS", "CARGO_BUILD_TARGET", "LD_PRELOAD", "RUST_TEST_NOCAPTURE",
                         "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUNNER"):
                self.assertNotIn(name, env)
            self.assertEqual(env["ARIADNE_BAP_CORE_DIR"], str(selected.core))
            self.assertEqual(env["RUSTC"], "/exact/rustc")
            core_env = native.core_environment(env | {"OCAMLPATH": "ambient"})
            self.assertNotIn("LD_LIBRARY_PATH", core_env)
            self.assertNotIn("OCAMLPATH", core_env)
            self.assertIn("LD_LIBRARY_PATH", env)

    def test_fresh_four_gate_lifecycle_binds_current_inputs_without_promoting_other_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            commands = []
            selected = config(temporary)
            result = native.qualify(selected, runner=runner(commands), inspect=lambda _: identity())
            self.assertTrue(result["nativeConsumerValidated"])
            self.assertTrue(result["sourcesStable"])
            self.assertTrue(result["testArtifactStable"])
            self.assertEqual(result["nativeCaptureInstances"], 1280)
            self.assertEqual([command[6] for command, _ in commands], [row[1] for row in native.TESTS])
            for command, kwargs in commands:
                self.assertIn("--release", command)
                self.assertIn("--exact", command)
                self.assertIn("--include-ignored", command)
                self.assertIn("--show-output", command)
                self.assertEqual(kwargs["env"]["CARGO_TARGET_DIR"], str(selected.output / "cargo"))
            for name in ("address32ProducerQualified", "sourceComplete", "vendorFullDenominator", "fullAmd64Coverage", "universalIsaValidation"):
                self.assertFalse(result[name])
            self.assertNotIn("finiteProjectionComplete", result)

    def test_source_or_tool_drift_after_fresh_tests_revokes_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            calls = []
            def inspect(_):
                value = identity()
                if calls:
                    value["sourceHashes"]["observer.rs"] = "c" * 64
                calls.append(True)
                return value
            result = native.qualify(config(temporary), runner=runner([]), inspect=inspect)
            self.assertFalse(result["nativeConsumerValidated"])
            self.assertFalse(result["sourcesStable"])
            self.assertIn("changed during execution", result["error"])

    def test_manifest_or_lock_drift_cannot_reuse_successful_native_test_output(self):
        for filename in ("Cargo.toml", "Cargo.lock"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as temporary:
                selected = config(temporary)
                source = Path(temporary) / filename
                source.write_text("initial source")
                def inspect(_):
                    value = identity()
                    value["sourceHashes"][filename] = native.sha(source)
                    return value
                def damage(_):
                    source.write_text("changed source")
                result = native.qualify(selected, runner=runner([], damage), inspect=inspect)
                self.assertFalse(result["nativeConsumerValidated"])
                self.assertIn("changed during execution", result["error"])

    def test_artifact_is_rehashed_after_the_final_source_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            selected = config(temporary)
            calls = []
            def inspect(_):
                if calls:
                    (selected.output / "cargo/release/deps/unit-test-artifact").write_bytes(b"changed artifact")
                calls.append(True)
                return identity()
            result = native.qualify(selected, runner=runner([]), inspect=inspect)
            self.assertFalse(result["nativeConsumerValidated"])
            self.assertFalse(result["testArtifactStable"])
            self.assertIn("after the last gate", result["error"])

    def test_timeout_rejects_nan_infinity_zero_and_negative_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            selected = config(temporary)
            for timeout in (float("nan"), float("inf"), 0, -1):
                selected.timeout = timeout
                with self.subTest(timeout=timeout), self.assertRaisesRegex(ValueError, "finite and positive"):
                    native.qualify(selected, runner=runner([]), inspect=lambda _: identity())

    def test_zero_test_or_failed_process_stops_before_native_credit(self):
        with tempfile.TemporaryDirectory() as temporary:
            commands = []
            def zero(result):
                result.stdout = result.stdout.replace("running 1 test", "running 0 tests")
            result = native.qualify(config(temporary), runner=runner(commands, zero), inspect=lambda _: identity())
            self.assertEqual(len(commands), 1)
            self.assertFalse(result["nativeConsumerValidated"])
            self.assertEqual(result["nativeCaptureInstances"], 0)

    def test_missing_prerequisite_or_timeout_writes_only_failed_assessment(self):
        for attack in ("prerequisite", "timeout"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temporary:
                def inspect(_):
                    if attack == "prerequisite":
                        raise ValueError("missing reviewed helper")
                    return identity()
                def run(command, **kwargs):
                    raise subprocess.TimeoutExpired(command, kwargs["timeout"])
                result = native.qualify(config(temporary), runner=run, inspect=inspect)
                self.assertFalse(result["nativeConsumerValidated"])
                self.assertTrue(result["error"])

    def test_saved_output_directory_is_never_a_pass_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            selected = config(temporary)
            selected.output.mkdir()
            (selected.output / "assessment.json").write_text('{"nativeConsumerValidated":true}')
            with self.assertRaisesRegex(ValueError, "fresh output"):
                native.qualify(selected, runner=runner([]), inspect=lambda _: identity())


if __name__ == "__main__":
    unittest.main()
