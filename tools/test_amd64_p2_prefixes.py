"""LOCK memory-direction controls and actual instruction-source ownership."""
import copy
import unittest

import amd64_p2_prefixes as prefix


class PrefixInventoryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = prefix.entry.read(prefix.INPUT)
        cls.fixture = prefix.entry.read(prefix.INPUT.parent/"p2-prefix-source-excerpt.json")
        cls.pages = {p["pdfPage"]:p for p in cls.fixture["pages"]}

    def check_owner(self, name, record=None, rows=None):
        return prefix.assess_lock_owner(name, record or self.pack["lock"][name], self.pages,
            self.fixture["normalized"]["entries"], self.fixture["normalized"]["rows"] if rows is None else rows)

    def test_actual_source_owners_and_all_selectors_are_replayed(self):
        for name,count in (("ADC",19),("CMPXCHG8B CMPXCHG16B",2),("XCHG",14)):
            result = self.check_owner(name)
            self.assertEqual(len(result["forms"]),count)
            self.assertEqual(result["sourceScopeConflict"],"p2:lock-list-disagreement")
            self.assertTrue(all(not r["registerAlternativeLock"] for r in result["forms"]))
        cmp16 = self.check_owner("CMPXCHG8B CMPXCHG16B")["forms"][1]
        self.assertEqual(cmp16["originalRow"]["encodingCells"],[])
        self.assertEqual(cmp16["encodingAndFeatureLegality"],"separate-P3-obligation")

    def test_register_alternative_and_read_only_memory_are_not_lock_eligible(self):
        self.assertTrue(prefix.lock_applicable("ADD reg/mem32, reg32",[0]))
        self.assertFalse(prefix.lock_applicable("ADD reg/mem32, reg32",[]))
        self.assertFalse(prefix.lock_applicable("ADD reg32, reg/mem32",[1]))
        self.assertFalse(prefix.lock_applicable("ADD EAX, imm32",[]))
        self.assertTrue(prefix.lock_applicable("CMPXCHG16B mem128",[0]))

    def test_smaller_operands_remain_eligible_under_native64_execution(self):
        for bits in (8,16,32,64):
            self.assertTrue(prefix.lock_applicable(f"ADC reg/mem{bits}, reg{bits}",[0]))
        with self.assertRaises(ValueError):
            prefix.lock_applicable("ADC reg/mem32, reg32",[0],"legacy32")

    def test_xchg_memory_in_either_source_syntax_is_implicitly_locked(self):
        for selector,position in (("XCHG reg/mem32, reg32",0),("XCHG reg32, reg/mem32",1)):
            self.assertTrue(prefix.lock_applicable(selector,[position]))
        checked = self.check_owner("XCHG")
        self.assertEqual(sum(f["automaticallyLockedMemory"] for f in checked["forms"]),8)

    def test_malformed_or_unowned_memory_predicates_fail(self):
        for selector,positions in (("CMP reg/mem32, reg32",[0]),("ADD reg/mem32, reg32",[1]),
            ("ADD reg/mem32, reg32",[True]),("ADD reg/mem32, reg32",[0,0]),
            ("ADD reg/mem32, reg32",[-1]),("ADD mystery, reg32",[0])):
            with self.subTest(selector=selector,positions=positions), self.assertRaises(ValueError):
                prefix.lock_applicable(selector,positions)

    def test_omitted_form_clause_swapped_owner_and_direction_forgery_fail(self):
        for attack in ("form", "predicate", "boolean", "owner", "clause", "cell", "selector"):
            record = copy.deepcopy(self.pack["lock"]["ADC"])
            if attack == "form": record["forms"].pop()
            elif attack == "predicate": record["forms"][-1]["memoryPositions"] = [1]
            elif attack == "boolean": record["forms"][4]["memoryPositions"] = [False]
            elif attack == "owner": record["owner"] = "amd-entry:0006"
            elif attack == "clause": record["clause"]["cells"].pop()
            elif attack == "cell": record["forms"][0]["sourceCell"] = record["forms"][1]["sourceCell"]
            else: record["forms"][0]["selector"] = "ADC reg/mem8, imm8"
            with self.subTest(attack=attack), self.assertRaises(ValueError): self.check_owner("ADC",record)

    def test_source_row_omission_is_not_certified_by_matching_fixture_count(self):
        rows = copy.deepcopy(self.fixture["normalized"]["rows"])
        rows.pop(0)
        with self.assertRaises(ValueError): self.check_owner("ADC",rows=rows)

    def test_repeat_data_size_and_counter_size_remain_separate(self):
        for name in prefix.REPEAT:
            contract = prefix.repeat_contract(name)
            self.assertEqual(contract,self.pack["repeat"][name]["properties"])
            self.assertEqual(contract["countBits"],[64,32])
            self.assertIn(8,contract["operandBits"])
            self.assertEqual(64 in contract["operandBits"], name not in {"INS","OUTS"})
            self.assertEqual(contract["prefixes"],["f3-repe-repz","f2-repne-repnz"] if name in {"CMPS","SCAS"} else ["f3-rep"])
        with self.assertRaises(ValueError): prefix.repeat_contract("SIMD-CMPSD")

    def test_subset_fixture_cannot_satisfy_whole_source_assessment(self):
        with self.assertRaisesRegex(ValueError,"source owners"):
            prefix.assess(list(self.pages.values()),self.fixture["normalized"])


if __name__ == "__main__":
    unittest.main()
