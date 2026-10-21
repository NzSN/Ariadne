"""Small adversarial controls for I5c timing evidence admission (no native run)."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_i5c_performance as gate


class PerformanceControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def presentation(self):
        value = {"conclusion": "unknown", "gaps": ["range", "byte"],
                 "evidence_requirements": ["Resolve range", "Resolve byte"],
                 "arithmetic": {"sum_before_reduction": "18446744073709551624"}}
        text = ("Ariadne address-wrap assessment (example)\nconclusion: Unknown\n"
                "gap: range\ngap: byte\nrequires: Resolve range\nrequires: Resolve byte\n"
                "conditional arithmetic under the declared premises:\n")
        (self.root / "address-wrap-assessment.txt").write_text(text)
        (self.root / "address-wrap-assessment.dot").write_text(
            "// address_wrap_assessment: " + json.dumps(value) + "\ndigraph AddressWrap {}\n")
        return value, text

    def test_frozen_cases_and_raw_integer_oracle(self):
        cases = gate.fixture_cases()
        self.assertEqual([case["case"] for case in cases], gate.contract()["fixtureCases"])
        indexed = {row["case"]: row for row in cases}
        self.assertEqual(indexed["mov32mi-underflow"]["oracle"]["conclusion"], "unknown")
        self.assertEqual(indexed["mov32mi-underflow"]["oracle"]["arithmetic"]["wrap_kind"], "lower")
        self.assertEqual(indexed["mov32mi-negative-zero"]["oracle"]["arithmetic"]["sum_before_reduction"], "0")

    def test_changed_contract_repeat_budget_or_inventory_rejected(self):
        frozen = gate.contract()
        for field, item in (("warmups", True), ("measuredRepeats", 4), ("maxPhaseMedianMs", 11),
                            ("maxCliMedianMs", 1501), ("maxEvidence", 63), ("maxClaims", 63),
                            ("fixtureCases", frozen["fixtureCases"][:-1]),
                            ("controlledCases", frozen["controlledCases"][::-1])):
            value = copy.deepcopy(frozen)
            value[field] = item
            with self.subTest(field=field), patch.object(gate, "read_json", return_value=value):
                with self.assertRaises(ValueError):
                    gate.contract()

    def test_exact_requirements_and_unknown_before_math(self):
        value, text = self.presentation()
        gate.validate_presentations(self.root, value)
        controls = [text.replace("requires: Resolve byte\n", ""),
                    text.replace("requires: Resolve range\nrequires: Resolve byte", "requires: Resolve byte\nrequires: Resolve range"),
                    text.replace("gap: byte\n", ""),
                    text.replace("conclusion: Unknown", "conclusion: RefutedUnderPremises"),
                    text.replace("conditional arithmetic under the declared premises:\n", "").replace(
                        "gap: range", "conditional arithmetic under the declared premises:\ngap: range")]
        for number, malformed in enumerate(controls):
            with self.subTest(control=number):
                (self.root / "address-wrap-assessment.txt").write_text(malformed)
                with self.assertRaises(ValueError):
                    gate.validate_presentations(self.root, value)

    def test_dot_embedded_report_substitution_rejected(self):
        value, _ = self.presentation()
        forged = {**value, "conclusion": "refuted_under_premises"}
        (self.root / "address-wrap-assessment.dot").write_text("// address_wrap_assessment: " + json.dumps(forged))
        with self.assertRaises(ValueError):
            gate.validate_presentations(self.root, value)

    def retained_call(self, binding=None):
        binding = binding or {"sourceCohortSha256": "source", "toolCohortSha256": "tool"}
        path = self.root / "call"
        path.mkdir()
        (path / "stdout").write_bytes(b"result\n")
        (path / "stderr").write_bytes(b"")
        receipt = {"command": ["selected-binary", "argument"], "cwd": str(gate.ROOT),
                   "exitCode": 0, "elapsedNs": 1000,
                   "stdoutSha256": gate.sha(path / "stdout"), "stderrSha256": gate.sha(path / "stderr"), **binding}
        gate.write_json(path / "call.json", receipt)
        return path, receipt, binding

    def test_raw_receipt_rejects_forged_status_timing_command_or_cohort(self):
        path, receipt, binding = self.retained_call()
        gate.call_receipt(path, receipt["command"], binding)
        for key, item in (("exitCode", True), ("exitCode", 1), ("elapsedNs", True), ("elapsedNs", 0),
                          ("elapsedNs", 120_000_000_000), ("command", ["different-binary", "argument"]),
                          ("sourceCohortSha256", "other-source"), ("toolCohortSha256", "other-tool"),
                          ("stdoutSha256", "0" * 64)):
            changed = {**receipt, key: item}
            gate.write_json(path / "call.json", changed)
            with self.subTest(key=key, value=item), self.assertRaises(ValueError):
                gate.call_receipt(path, receipt["command"], binding)
        gate.write_json(path / "call.json", receipt)
        (path / "unlisted").write_text("unlisted")
        with self.assertRaises(ValueError):
            gate.call_receipt(path, receipt["command"], binding)

    def test_changed_raw_stream_and_symlink_rejected(self):
        path, receipt, binding = self.retained_call()
        (path / "stdout").write_text("substituted")
        with self.assertRaises(ValueError):
            gate.call_receipt(path, receipt["command"], binding)
        (self.root / "link").symlink_to(path)
        with self.assertRaises(ValueError):
            gate.files_under(self.root)

    def test_codec_authentication_must_execute_selected_binary_again(self):
        output = self.root / "output"
        output.mkdir()
        for name in gate.OUTPUT_NAMES:
            (output / name).write_text(name)
        assessment = {"scope_id": "scope", "content_id": "content", "evidence": [], "claims": [], "conclusion": "unknown"}
        identity = {"sourceCohortSha256": "source", "toolCohortSha256": "tool"}
        binding = gate.codec_binding(output, identity)
        path, receipt, _ = self.retained_call(binding)
        command = gate.codec_command("selected-binary", output)
        expected = gate.codec_result(output, assessment)
        (path / "stdout").write_text(json.dumps(expected))
        receipt.update(command=command, stdoutSha256=gate.sha(path / "stdout"))
        gate.write_json(path / "call.json", receipt)
        # Retained self-claims are insufficient when the current real decoder
        # rejects. This control tests orchestration, not Rust codec semantics.
        with patch.object(gate.subprocess, "run", return_value=subprocess.CompletedProcess(command, 1, b"", b"rejected")) as invoked:
            with self.assertRaises(ValueError):
                gate.authenticate_codec("selected-binary", output, path, identity, assessment, fresh=True)
            self.assertEqual(invoked.call_args.args[0], command)
            self.assertEqual(invoked.call_count, 1)
        with patch.object(gate.subprocess, "run", return_value=subprocess.CompletedProcess(command, 0, b'{"passed":true}', b"")):
            with self.assertRaises(ValueError):
                gate.authenticate_codec("selected-binary", output, path, identity, assessment, fresh=True)

    def test_source_tool_or_exact_report_substitution_invalidates_codec_receipt(self):
        output = self.root / "output"
        output.mkdir()
        for name in gate.OUTPUT_NAMES:
            (output / name).write_text(name)
        identity = {"sourceCohortSha256": "source", "toolCohortSha256": "tool"}
        binding = gate.codec_binding(output, identity)
        path, receipt, _ = self.retained_call(binding)
        command = gate.codec_command("selected-binary", output)
        receipt["command"] = command
        gate.write_json(path / "call.json", receipt)
        for changed_identity in ({**identity, "sourceCohortSha256": "changed"},
                                 {**identity, "toolCohortSha256": "changed"}):
            with self.assertRaises(ValueError):
                gate.call_receipt(path, command, gate.codec_binding(output, changed_identity))
        (output / "address-wrap-assessment.json").write_text("different exact report")
        with self.assertRaises(ValueError):
            gate.call_receipt(path, command, gate.codec_binding(output, identity))

    def test_duplicate_and_nonfinite_json_rejected(self):
        for text in ('{"run":1,"run":2}', '{"elapsedNs":NaN}', '{"elapsedNs":Infinity}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                gate.strict_json(text)


if __name__ == "__main__":
    unittest.main()
