"""Independent controls for repeated-string observation and its execution bound."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import check_bap_repeated_string_oracle as oracle


class RepeatedStringObserverControls(unittest.TestCase):
    def test_zero_count_does_not_require_memory_or_change_flags(self):
        for operation in ("movsb", "stosb", "cmpsb"):
            registers, memory = oracle.scenario(0, 1, 1, "source-wrap", "first-diff")
            self.assertEqual(memory, {})
            oracle.check_case({"name": operation, "operation": operation}, [], registers, memory)

    def test_omitted_loop_is_detected_for_nonzero_count(self):
        for operation in ("movsb", "stosb", "cmpsb"):
            registers, memory = oracle.scenario(4, 0, 1, "disjoint", "late-diff")
            with self.assertRaises(ValueError):
                oracle.check_case({"name": operation, "operation": operation}, [], registers, memory)

    def test_reference_distinguishes_early_stop_from_prior_zero_flag(self):
        registers, memory = oracle.scenario(4, 0, 0, "disjoint", "late-diff")
        after, unchanged = oracle.expected("cmpsb", registers, memory)
        self.assertEqual(after["RCX"], 1)
        self.assertEqual(after["RSI"], 0x7003)
        self.assertEqual(after["ZF"], 0)
        self.assertEqual(unchanged, memory)

    def test_nonterminating_loop_fails_instead_of_partial_success(self):
        evaluator = oracle.LoopEvaluator({}, {}, limit=3)
        with self.assertRaisesRegex(ValueError, "execution bound"):
            evaluator.statements([{"kind": "while", "condition": {"kind": "int", "value": "1:1u"}, "body": []}])


if __name__ == "__main__":
    unittest.main()
