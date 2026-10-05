"""Exercise active gate decisions without native tools or retired ISA files."""
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parent


class ActiveQualificationTests(unittest.TestCase):
    def run_gate(self, name, *, failure=False, stable=True, windows=False):
        spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            work.mkdir()
            for relative, data in {
                "native/bap/toolchain.lock.json": {},
                "evidence/Ariadne/bap-windows-workload-case.json": {},
                "mbt/stage-e/results/latest.json": {"sourceHashes": {}},
                "mbt/stage-e/corpus/manifest.json": {
                    "generation": {"nativeHelperSha256": "test-digest"}
                },
            }.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                self.assertFalse(any("amd64" in arg or "register-core" in arg
                                     for arg in command), command)
                output = ""
                # Nested records are controlled fixtures, not qualification evidence.
                if command[0] == "python3":
                    record = work / f"nested-{len(calls)}.json"
                    record.write_text(json.dumps({
                        "passed": True,
                        "windows98Checked": windows,
                        "defaultPromotionEligible": windows,
                    }))
                    output = f"Report: {record}\n"
                code = 1 if failure and command[:2] == ["cargo", "test"] else 0
                return subprocess.CompletedProcess(command, code, output, "")

            before = {"source": "before"}
            after = before if stable else {"source": "changed"}
            with ExitStack() as stack:
                stack.enter_context(patch.object(module, "ROOT", root))
                if hasattr(module, "SPECS"):
                    stack.enter_context(patch.object(module, "SPECS", root / "Specs"))
                stack.enter_context(patch.object(module, "sources", side_effect=[before, after]))
                if hasattr(module, "sha"):
                    stack.enter_context(patch.object(module, "sha", return_value="test-digest"))
                if hasattr(module, "active_identity"):
                    stack.enter_context(patch.object(module, "active_identity", return_value=None))
                # This test owns orchestration, not workload admission. The
                # workload suites separately exercise complete raw evidence,
                # inventory checks and the real qualification predicate.
                if hasattr(module, "validate_workload_bindings"):
                    stack.enter_context(patch.object(module, "validate_workload_bindings"))
                    stack.enter_context(patch.object(module, "windows_qualification",
                                                     return_value={"targetMet": windows,
                                                                   "reason": "controlled prerequisite"}))
                    stack.enter_context(patch.object(module, "WINDOWS_CASE_PATH",
                                                     root / "evidence/Ariadne/bap-windows-workload-case.json"))
                stack.enter_context(patch.object(module.subprocess, "run", side_effect=run))
                stack.enter_context(patch.object(module.tempfile, "mkdtemp", return_value=str(work)))
                stack.enter_context(patch.dict("os.environ", {"ARIADNE_DOT": str(root / "dot")}))
                stack.enter_context(patch("sys.argv", [name]))
                stack.enter_context(redirect_stdout(io.StringIO()))
                with self.assertRaises(SystemExit) as exit_result:
                    module.main()
            report = json.loads((work / "report.json").read_text())
            expected = stable and not failure
            self.assertEqual(exit_result.exception.code, 0 if expected else 1)
            self.assertEqual(report["passed"], expected)
            self.assertNotIn("registerCoreAcceptance", report)
            self.assertIn("retired", report["instructionStepTrack"])
            self.assertTrue(calls)
            return report

    def test_active_gates_without_isa_files(self):
        for name in ("check_b_f_progress", "check_stage_e", "check_bap_semantics"):
            for failure, stable in ((False, True), (True, True), (False, False)):
                with self.subTest(gate=name, failure=failure, stable=stable):
                    self.run_gate(name, failure=failure, stable=stable)

    def test_windows_qualification_remains_required(self):
        for windows in (False, True):
            with self.subTest(windows=windows):
                report = self.run_gate("check_bap_semantics", windows=windows)
                self.assertTrue(report["implementationGatesPassed"])
                self.assertEqual(report["stage1ExitPassed"], windows)
                self.assertEqual(report["stage2PrerequisiteSatisfied"], windows)
                self.assertEqual(report["defaultPromotionEligible"], windows)
                self.assertEqual(bool(report["missing"]), not windows)
                self.assertFalse(report["stage2Qualified"])

    def test_effects_inventory_preserves_analysis_and_manual_provenance(self):
        import check_effects

        sources = check_effects.sources()
        for path in ("Specs/Ariadne.tla", "Specs/AriadneEffects.tla",
                     "Specs/AriadneTypes.tla", "Specs/AriadneMachineCommon.tla",
                     "Specs/Effects.cfg", "Specs/AMD64/manuals.lock.json"):
            self.assertIn(path, sources)
        self.assertFalse(any(Path(path).name.startswith(
            ("AMD64", "AriadneX86_64", "X86_64")) for path in sources))


if __name__ == "__main__":
    unittest.main()
