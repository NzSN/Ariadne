"""Controls proving the numeric observer detects plausible producer defects."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import check_bap_bit_count_oracle as oracle


def var(name, index=0, virtual=False, width=64):
    return {"name": name, "index": index, "virtual": virtual, "type": "imm", "width": width}


def integer(value, width):
    return {"kind": "int", "value": f"{value}:{width}u"}


def move(name, value, width=64):
    return {"kind": "move", "var": var(name, width=width), "value": integer(value, width)}


class BitCountObserverControls(unittest.TestCase):
    def test_zero_input_distinguishes_count_from_undefined_scan(self):
        for width in (16, 32, 64):
            self.assertEqual(oracle.expected("lzcnt", width, 0), (width, {"CF": 1, "ZF": 0}))
            self.assertEqual(oracle.expected("tzcnt", width, 0), (width, {"CF": 1, "ZF": 0}))
        self.assertEqual(oracle.expected("lzcnt", 64, 1), (63, {"CF": 0, "ZF": 0}))
        self.assertEqual(oracle.expected("tzcnt", 64, 1), (0, {"CF": 0, "ZF": 1}))

    def test_virtual_names_do_not_alias_architectural_registers(self):
        evaluator = oracle.IdentityEvaluator({"RAX": oracle.Value(123, 64)}, {})
        evaluator.statements([
            {"kind": "move", "var": var("RAX", 1, True), "value": integer(7, 64)},
            {"kind": "move", "var": var("RAX", 2, True), "value": integer(9, 64)},
        ])
        self.assertEqual(evaluator.values["RAX"].n, 123)
        self.assertEqual(evaluator.values[("RAX", 1, True)].n, 7)
        self.assertEqual(evaluator.values[("RAX", 2, True)].n, 9)

    def test_bad_result_flag_and_unrelated_write_are_detected(self):
        case = {"name": "tzcnt-control", "width": 32, "source": "register", "operation": "tzcnt"}
        correct = [move("RAX", 3), move("CF", 0, 1), move("ZF", 0, 1)]
        oracle.check_case(case, correct, 8, 1)
        for position, wrong in [(0, 4), (1, 1), (2, 1)]:
            mutant = copy.deepcopy(correct)
            mutant[position]["value"] = integer(wrong, 64 if position == 0 else 1)
            with self.assertRaises(ValueError):
                oracle.check_case(case, mutant, 8, 1)
        with self.assertRaisesRegex(ValueError, "RCX"):
            oracle.check_case(case, correct + [move("RCX", 0)], 8, 1)

    def test_partial_destination_preserves_high_bytes(self):
        case = {"name": "tzcnt16-control", "width": 16, "source": "memory", "operation": "tzcnt"}
        with self.assertRaisesRegex(ValueError, "RAX"):
            oracle.check_case(case, [move("RAX", 3), move("CF", 0, 1), move("ZF", 0, 1)], 8, 0)


if __name__ == "__main__":
    unittest.main()
