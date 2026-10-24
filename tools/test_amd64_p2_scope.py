"""Scope controls preserve raw observations and independent width dimensions."""
import copy
import unittest

import amd64_p2_scope as scope


class Fixed64ScopeControls(unittest.TestCase):
    def setUp(self):
        self.pack = scope.entry.read(scope.INPUT)
        self.pages = scope.entry.read(scope.INPUT.parent / "p2-fixed64-source-excerpt.json")["pages"]
        self.originals = scope.entry.read(scope.native.INPUT)["default64Qualifications"]

    def assess(self, pack=None, pages=None, originals=None):
        return scope.assess(self.pack if pack is None else pack, self.pages if pages is None else pages,
                            self.originals if originals is None else originals)

    def test_seven_groups_keep_originals_and_other_smaller_operands(self):
        result = self.assess()
        selected = [r for r in result["qualifications"] if "currentScope" in r]
        self.assertEqual([r["currentScope"]["mnemonic"] for r in selected], list(scope.NEAR))
        self.assertEqual([r["original"] for r in result["qualifications"]], self.originals)
        self.assertTrue(all(r["originalSha256"] == scope.digest(r["original"]) for r in result["qualifications"]))
        self.assertTrue(all(r["currentScope"]["prefix66"] == "no-byte-removal-or-automatic-admission" for r in selected))
        push = next(r for r in result["qualifications"] if r["original"]["mnemonic"] == "PUSH imm32")
        self.assertNotIn("currentScope", push)
        self.assertIn("16-bit-under-66h", push["original"]["properties"]["immediateEncoding"])

    def test_address_count_displacement_and_stack_are_distinct(self):
        loop = scope.selected_contract("LOOP")
        self.assertEqual((loop["selectedOperandBits"], loop["addressBits"], loop["countBits"],
                          loop["relativeDisplacementBits"]), (64, [64, 32], [64, 32], [8]))
        self.assertIsNone(loop["returnAddressStackBits"])
        call = scope.selected_contract("CALL")
        self.assertEqual((call["relativeDisplacementBits"], call["returnAddressStackBits"]), ([32], 64))

    def test_forged_modes_owners_blanket_exclusions_or_prefix_admission_fail(self):
        for attack in ("mode", "owner", "operand", "count", "displacement", "address", "prefix", "extra", "omission", "all"):
            pack = copy.deepcopy(self.pack)
            row = pack["contracts"][0]
            if attack == "mode": pack["executionModes"] = ["host-64"]
            elif attack == "owner": row["owner"] = "amd-entry:0032"
            elif attack == "operand": row["selectedOperandBits"] = True
            elif attack == "count": pack["contracts"][4]["countSelectedBy"] = "operand-size"
            elif attack == "displacement": row["relativeDisplacementBits"] = [64]
            elif attack == "address": row["addressBits"] = [64]
            elif attack == "prefix": row["prefix66"] = "ignore-byte"
            elif attack == "extra": pack["complete"] = True
            elif attack == "omission": pack["contracts"].pop()
            else: row["excludedOperandAlternatives"] = [8, 16, 32]
            with self.subTest(attack=attack), self.assertRaises(ValueError): self.assess(pack=pack)

    def test_changed_original_or_source_conflict_is_rejected(self):
        originals = copy.deepcopy(self.originals)
        originals[0]["properties"]["operand16"] = "source-corrected"
        with self.assertRaises(ValueError): self.assess(originals=originals)
        pack = copy.deepcopy(self.pack)
        del pack["sourceClauses"]["pdf:128:cell:36"]
        with self.assertRaises(ValueError): self.assess(pack=pack)
        pages = copy.deepcopy(self.pages)
        pages[0]["cells"][36]["text"] = "64"
        with self.assertRaises(ValueError): self.assess(pages=pages)
        with self.assertRaises(ValueError): scope.selected_contract("PUSH imm32")


if __name__ == "__main__":
    unittest.main()
