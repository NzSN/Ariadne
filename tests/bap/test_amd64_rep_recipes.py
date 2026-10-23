#!/usr/bin/env python3
"""Memory-string recipe and independent numeric-oracle regression controls."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from amd64_rep_recipes import RECIPES, load_recipes
from check_bap_admission_oracle import Value
from check_bap_repeated_string_oracle import expected_recipe, scenario_recipe, subtract_flags


class RecipeContract(unittest.TestCase):
    def test_selected_tuples_and_explicit_missing_lifts(self):
        cases = load_recipes()["cases"]
        self.assertEqual(len(cases), 28)
        self.assertEqual(sum(case["profile"] is not None for case in cases), 24)
        self.assertEqual({case["elementBits"] for case in cases if case["profile"] is None}, {8, 16, 32, 64})
        self.assertTrue(all(case["family"] == "lods" for case in cases if case["profile"] is None))

    def reject(self, change):
        document = json.loads(RECIPES.read_text())
        change(document)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recipes.json"
            path.write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                load_recipes(path)

    def test_profile_cannot_admit_missing_lods_lift(self):
        self.reject(lambda doc: doc["cases"][8].update(profile="bap-bit-provenance-v13"))

    def test_address_and_element_widths_are_independent(self):
        self.reject(lambda doc: doc["cases"][1].update(addressBits=16))
        self.reject(lambda doc: doc["cases"][1].update(elementBits=32))
        self.reject(lambda doc: doc["cases"][1].update(countBits=32))

    def test_exact_prefix_and_opcode_binding(self):
        for encoded in ["f366a5", "67f3a5", "64f3a5", "f3f3a5", "f348a4"]:
            self.reject(lambda doc, encoded=encoded: doc["cases"][1].update(bytes=encoded))
        self.reject(lambda doc: doc["cases"][2].update(bapOpcode="MOVSD"))
        self.reject(lambda doc: doc["cases"][12].update(repeatCondition="not-equal"))

    def test_duplicate_recipe_or_missing_manual_binding_is_refused(self):
        self.reject(lambda doc: doc["cases"].__setitem__(1, copy.deepcopy(doc["cases"][0])))
        self.reject(lambda doc: doc["cases"][0].update(manualPdfPages=[54]))
        self.reject(lambda doc: doc["sources"]["amd-24594-r3.38"].update(sha256="0" * 64))


class SequentialEquations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_recipes()["cases"]

    def case(self, family, bits, repeat="count"):
        return next(case for case in self.cases if case["family"] == family
                    and case["elementBits"] == bits and case["repeatCondition"] == repeat)

    def state(self, case, count=1, accumulator=0xA51234879BCD0123):
        return scenario_recipe(case, count, 0, 1, "disjoint", "equal", accumulator)

    def test_zero_count_preserves_all_register_lanes_flags_and_memory(self):
        for case in self.cases:
            registers, memory = self.state(case, count=0)
            actual, actual_memory = expected_recipe(case, registers, memory)
            self.assertEqual(actual, {key: value.n for key, value in registers.items()})
            self.assertEqual(actual_memory, memory)

    def test_lods_lane_equations_do_not_create_producer_permission(self):
        for bits in [8, 16, 32, 64]:
            case = self.case("lods", bits)
            registers, memory = self.state(case)
            source = registers["RSI"].n
            for lane in range(bits // 8):
                memory[source + lane] = 0x80 + lane
            expected_low = sum((0x80 + lane) << (lane * 8) for lane in range(bits // 8))
            actual, _ = expected_recipe(case, registers, memory)
            expected_rax = ((registers["RAX"].n & ~((1 << bits) - 1)) | expected_low
                            if bits < 32 else expected_low)
            self.assertEqual(actual["RAX"], expected_rax)
            self.assertIsNone(case["profile"])

    def test_scas_continuation_uses_new_zero_flag(self):
        for repeat, initial_zf, second_equal in [("equal", 0, False), ("not-equal", 1, True)]:
            case = self.case("scas", 16, repeat)
            registers, memory = self.state(case, count=4, accumulator=0xAABBCCDD12345678)
            registers["ZF"] = Value(initial_zf, 1)
            destination = registers["RDI"].n
            # REPE compares equal then differs; REPNE differs then equals.
            first = 0x5679 if second_equal else 0x5678
            second = 0x5678 if second_equal else 0x5679
            memory[destination], memory[destination + 1] = first & 255, first >> 8
            memory[destination + 2], memory[destination + 3] = second & 255, second >> 8
            actual, actual_memory = expected_recipe(case, registers, memory)
            self.assertEqual(actual["RCX"], 2)
            self.assertEqual(actual["RDI"], destination + 4)
            self.assertEqual(actual["RAX"], registers["RAX"].n)
            self.assertEqual(actual["ZF"], int(second_equal))
            self.assertEqual(actual_memory, memory)

    def test_overlapping_word_reads_whole_source_before_store(self):
        case = self.case("movs", 16)
        registers, memory = self.state(case, count=2)
        registers["RSI"], registers["RDI"] = Value(0x100, 64), Value(0x101, 64)
        memory = {0x100: 1, 0x101: 2, 0x102: 3, 0x103: 4, 0x104: 5}
        actual, actual_memory = expected_recipe(case, registers, memory)
        self.assertEqual(actual_memory, {0x100: 1, 0x101: 1, 0x102: 2, 0x103: 2, 0x104: 4})
        self.assertEqual(actual["RCX"], 0)

    def test_multibyte_wrap_and_negative_direction(self):
        case = self.case("stos", 32)
        registers, memory = self.state(case, count=2, accumulator=0xFFEEDDCC44332211)
        registers["RDI"], registers["DF"] = Value((1 << 64) - 2, 64), Value(1, 1)
        actual, actual_memory = expected_recipe(case, registers, memory)
        self.assertEqual(actual["RDI"], (1 << 64) - 10)
        self.assertEqual([actual_memory[key] for key in [(1 << 64) - 2, (1 << 64) - 1, 0, 1]], [0x11, 0x22, 0x33, 0x44])

    def test_parity_is_low_byte_and_overflow_is_element_width(self):
        self.assertEqual(subtract_flags(0x100, 0, 16)["PF"], 1)
        self.assertEqual(subtract_flags(0x8000, 1, 16)["OF"], 1)
        self.assertEqual(subtract_flags(0x80000000, 1, 32)["OF"], 1)


if __name__ == "__main__":
    unittest.main()
