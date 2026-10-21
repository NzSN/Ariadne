"""Controls that prevent compact receipts from overstating exercised tests."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

import run_generated_validation as validation


class GeneratedValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name) / "run"
        self.tools = patch.object(validation, "tool_identities", return_value={"python": "test"})
        self.tools.start()
        self.addCleanup(self.tools.stop)

    def suite(self, code, **kwargs):
        return dict(name="control", command=[sys.executable, "-c", code], **kwargs)

    def test_success_writes_small_receipt_without_raw_archive(self):
        suite = self.suite("print('test result: ok. 3 passed; 0 failed; 0 ignored;')",
                           expectedTests=3, generatedCasesPerTest=32)
        row = validation.run_suites(self.work, [suite], identity=lambda: {"source": "x"})
        self.assertTrue(row["passed"])
        self.assertEqual(row["generatedCases"], 96)
        self.assertIn("TLA+-generated MirrorRust replay", row["unexercised"])
        self.assertFalse((self.work / "raw-evidence.tar.gz").exists())
        self.assertLess((self.work / "receipt.json").stat().st_size, 4096)

    def test_fewer_or_ignored_tests_cannot_pass(self):
        for count, ignored in ((0, 0), (2, 0), (3, 1)):
            with self.subTest(count=count, ignored=ignored):
                directory = self.work / f"case-{count}-{ignored}"
                suite = self.suite(f"print('test result: ok. {count} passed; 0 failed; {ignored} ignored;')",
                                   expectedTests=3, generatedCasesPerTest=32)
                row = validation.run_suites(directory, [suite], identity=lambda: {})
                self.assertFalse(row["passed"])
                self.assertNotIn("rawArchive", row)

    def test_failure_timeout_and_source_drift_remain_failures(self):
        for label, code, identities, timeout in (
                ("failure", "raise SystemExit(2)", ({}, {}), 5),
                ("timeout", "import time;time.sleep(10)", ({}, {}), 0.01),
                ("drift", "print('done')", ({"a": "old"}, {"a": "new"}), 5)):
            with self.subTest(label=label):
                identities = iter(identities)
                row = validation.run_suites(self.work / label, [self.suite(code)],
                                            identity=lambda: next(identities), timeout=timeout)
                self.assertFalse(row["passed"])
                self.assertNotIn("rawArchive", row)
                self.assertTrue((self.work / label / "control.stderr").exists())

    def test_all_run_outputs_stay_unarchived(self):
        row = validation.run_suites(self.work, [self.suite('pass')], identity=lambda: {})
        self.assertTrue(row['passed'])
        self.assertNotIn('rawArchive', row)
        self.assertFalse(list(self.work.glob('*.tar.gz')))

    def test_mbt_tiers_and_seed_case_configuration_are_explicit(self):
        suites = validation.suite_plan([7, 9], 32, "all")
        core = [suite for suite in suites if suite["name"].startswith("core-")]
        self.assertEqual(core[0]["environment"]["ARIADNE_CORE_PROPERTY_SEED"], "7")
        self.assertEqual(core[1]["environment"]["ARIADNE_CORE_PROPERTY_CASES"], "32")
        self.assertEqual([s["name"] for s in suites[-2:]],
                         ["tlaplus-core-replay", "tlaplus-stage-e-replay"])

    def test_work_directory_cannot_reuse_a_previous_run(self):
        self.work.mkdir()
        with self.assertRaises(FileExistsError):
            validation.run_suites(self.work, [], identity=lambda: {})

    def test_stale_nested_replay_report_cannot_supply_success(self):
        replay = Path(self.temp.name) / "old-report.json"
        replay.write_text('{"passed":true}')
        suite = self.suite("pass", replayReport=str(replay))
        row = validation.run_suites(self.work, [suite], identity=lambda: {})
        self.assertFalse(row["passed"])
        self.assertIn("fresh replay report", row["suites"][0]["error"])
        self.assertFalse(replay.exists())

    def test_tool_drift_cannot_supply_success(self):
        with patch.object(validation, "tool_identities", side_effect=[{"tool": "old"}, {"tool": "new"}]):
            row = validation.run_suites(self.work, [self.suite("pass")], identity=lambda: {})
        self.assertFalse(row["passed"])
        self.assertFalse(row["toolsStable"])

    def test_core_replay_mutations_keep_unique_live_source_seams(self):
        source = (validation.ROOT / "src/engine.rs").read_text()
        rows = json.loads((validation.ROOT / "mbt/mutations.json").read_text())
        self.assertEqual(len(rows), 5)
        for row in rows:
            with self.subTest(mutation=row["name"]):
                self.assertEqual(source.count(row["old"]), 1)
                self.assertNotEqual(row["old"], row["new"])


if __name__ == "__main__":
    unittest.main()
