"""Default64 row ownership, mixed-mode exclusions and independent dimensions."""
import copy
import unittest
from unittest.mock import patch

import amd64_p2_default64 as d
import amd64_p2_constraints as p2


class Default64Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack=d.entry.read(d.INPUT)
        cls.fixture=d.entry.read(d.INPUT.parent/"p2-default64-source-excerpt.json")

    def check(self,owner,record=None,source=None):
        source=self.fixture if source is None else source
        return d.assess_owner(self.pack["owners"][owner] if record is None else record,source["pages"],source["entries"])

    def test_italic_operands_use_baseline_order_and_preserve_mov_direction(self):
        enter=self.check("ENTER")
        self.assertEqual(enter["tables"][0]["rows"][0]["selector"],"ENTER imm16, 0")
        self.assertEqual(enter["tables"][0]["rows"][0]["sourceEncoding"],"C8 iw 00")
        cr=self.check("MOV CRn")
        self.assertEqual(cr["tables"][0]["rows"][2]["selector"],"MOV reg32, CRn")
        self.assertEqual(cr["tables"][0]["rows"][2]["sourceEncoding"],"0F 20 /r")

    def test_source_width32_is_not_native64_but_address32_is(self):
        rows=self.check("JCXZ JECXZ JRCXZ")["forms"]
        self.assertEqual([r["properties"]["state"] for r in rows],
                         ["excluded-selected-execution-mode","native64-source-form","native64-source-form"])
        self.assertEqual(rows[1]["properties"]["countBits"],[32])
        self.assertEqual(rows[1]["properties"]["currentOperandBits"],[64])
        self.assertEqual(rows[2]["properties"]["countBits"],[64])

    def test_leave_identical_selector_rows_have_distinct_source_qualifiers(self):
        rows=self.check("LEAVE")["forms"]
        self.assertEqual([r["selector"] for r in rows],["LEAVE"]*3)
        self.assertEqual([r["properties"]["sourceOperandBits"] for r in rows],[16,32,64])
        self.assertEqual(rows[0]["properties"]["currentOperandBits"],[16])
        self.assertEqual(rows[0]["properties"]["sourceDescriptionStackPointerBits"],16)
        self.assertEqual(rows[0]["properties"]["stackPointerBits"],64)
        self.assertEqual(rows[1]["properties"]["state"],"excluded-selected-execution-mode")
        self.assertEqual(rows[2]["properties"]["currentOperandBits"],[64])

    def test_push_source_imm64_is_encoded_id_and_does_not_widen_immediate(self):
        rows={r["selector"]:r for r in self.check("PUSH")["forms"]}
        self.assertEqual(rows["PUSH imm64"]["sourceEncoding"],"68 id")
        self.assertEqual(rows["PUSH imm64"]["properties"]["encodedImmediateBits"],32)
        self.assertEqual(rows["PUSH imm64"]["properties"]["currentOperandBits"],[64])
        self.assertEqual(rows["PUSH imm32"]["properties"]["state"],"excluded-selected-execution-mode")
        self.assertEqual(rows["PUSH imm8"]["properties"]["currentOperandBits"],[16,64])
        self.assertEqual(rows["PUSH imm8"]["properties"]["encodedImmediateBits"],8)
        self.assertEqual(rows["PUSH FS"]["properties"]["selectorBits"],16)
        self.assertEqual(rows["PUSH FS"]["properties"]["stackSlotBits"],[16,64])
        self.assertFalse(rows["PUSH FS"]["properties"]["stackSlotIsSelectorWidth"])
        self.assertEqual(rows["PUSH DS"]["properties"]["state"],"excluded-selected-execution-mode")

    def test_fixed_system_no_rex_entries_do_not_share_one_operand_size_rule(self):
        lgdt=self.check("LGDT")["forms"]
        self.assertEqual(lgdt[0]["properties"]["state"],"excluded-selected-execution-mode")
        self.assertEqual(lgdt[1]["properties"]["native64PseudoDescriptorBytes"],10)
        self.assertEqual(lgdt[1]["properties"]["limitBits"],16)
        lldt=self.check("LLDT")["forms"][0]
        self.assertEqual(lldt["sourceEncoding"],"0F 00 /2")
        self.assertEqual(lldt["properties"]["currentOperandBits"],[16])
        self.assertEqual(lldt["properties"]["descriptorBaseBits"],64)
        self.assertEqual(lldt["properties"]["descriptorObjectBytes"],16)
        cr=self.check("MOV CRn")["forms"]
        self.assertEqual(sum(r["properties"]["state"]=="native64-source-form" for r in cr),4)
        self.assertEqual(cr[5]["properties"]["featureRequired"],"CPUID.Fn8000_0001.ECX.AltMovCr8=1")
        self.assertIn("not-memory-lock",cr[5]["properties"]["prefixF0"])

    def test_b1_fixed64_stores_are_covered_even_though_absent_from_no_rex_list(self):
        for name in ("SGDT","SIDT"):
            rows=self.check(name)["forms"]
            self.assertEqual(rows[0]["properties"]["state"],"excluded-selected-execution-mode")
            self.assertEqual(rows[1]["properties"]["currentOperandBits"],[64])
            self.assertEqual(rows[1]["properties"]["native64PseudoDescriptorBytes"],10)
            self.assertEqual(rows[1]["properties"]["prefix66"],"ignored-in-native64")
            self.assertNotIn(name,p2.NO_REX)

    def test_b1_push_families_partition_actual_stack_and_segment_forms(self):
        checked=self.check("PUSH")
        records=[r for r in p2.entry.read(p2.sizes.INPUT)["rows"] if p2.sizes.family(r["heading"]["text"])=="PUSH"]
        links=[p2.p2c.default_b1_forms(r,dict(owners={"PUSH":checked})) for r in records]
        self.assertEqual([link["sourceForms"] for link in links],[10,6])
        self.assertFalse(set(links[0]["sourceRowOrdinals"])&set(links[1]["sourceRowOrdinals"]))
        self.assertEqual(set(links[0]["sourceRowOrdinals"]+links[1]["sourceRowOrdinals"]),set(range(16)))
        self.assertIn("PUSH imm64",links[0]["selectors"])
        self.assertIn("PUSH FS",links[1]["selectors"])

    def test_selected_near16_exclusions_do_not_exclude_word_stack_operations(self):
        self.assertEqual(d.form_contract("CALL (Near)",0)["state"],"excluded-selected-fixed64-hypothesis")
        self.assertEqual(d.form_contract("CALL (Near)",3)["state"],"excluded-selected-execution-mode")
        self.assertEqual(d.form_contract("CALL (Near)",1)["relativeDisplacementBits"],32)
        self.assertEqual(d.form_contract("PUSH",0)["currentOperandBits"],[16])
        self.assertEqual(d.form_contract("RET (Near)",1)["encodedImmediateBits"],16)
        self.assertEqual(d.form_contract("RET (Near)",1)["returnAddressSlotBits"],64)

    def test_form_omission_width_prefix_scope_and_qualifier_swap_fail(self):
        for attack in ("form","ordinal","width","address","prefix","group","qualifier","flag"):
            record=copy.deepcopy(self.pack["owners"]["LEAVE"])
            if attack=="form":record["forms"].pop()
            elif attack=="ordinal":record["forms"][0]["sourceRowOrdinal"]=2
            elif attack=="width":record["forms"][0]["properties"]["currentOperandBits"]=[64]
            elif attack=="address":record["forms"][0]["properties"]["stackPointerBits"]=16
            elif attack=="prefix":record["forms"][0]["properties"]["extraPrefixAdmission"]=True
            elif attack=="group":record["forms"][0]["b5Group"]="CALL"
            elif attack=="qualifier":record["qualifiers"]["0"]=record["qualifiers"]["2"]
            else:record["complete"]=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):self.check("LEAVE",record)

    def test_physical_word_swap_page_omission_and_owner_substitution_fail(self):
        for attack in ("word","page","owner"):
            source=copy.deepcopy(self.fixture)
            if attack=="page":source["pages"]=[p for p in source["pages"] if p["pdfPage"]!=340]
            elif attack=="owner":next(e for e in source["entries"] if e["title"]=="PUSH")["title"]="POP"
            else:
                page=next(p for p in source["pages"] if p["pdfPage"]==339)
                cell=next(c for c in page["cells"] if c["id"]=="pdf:339:cell:58")
                cell["wordBoxes"][0]["rect"][0]+=1
                cell["wordBoxesSha256"]=d.digest(cell["wordBoxes"])
            with self.subTest(attack=attack),self.assertRaises(ValueError):self.check("PUSH",source=source)

    def test_independent_scan_rejects_shifted_co_omitted_physical_row(self):
        specs=copy.deepcopy(d.SPECS)
        ident,first,last,forms=specs["PUSH"]
        specs["PUSH"]=(ident,first,last,forms[:-1])
        pages=copy.deepcopy(self.fixture["pages"])
        page=next(p for p in pages if p["pdfPage"]==340)
        cell=next(c for c in page["cells"] if c["id"]=="pdf:340:cell:21")
        for w in cell["wordBoxes"]:
            w["rect"][0]+=6
            w["rect"][2]+=6
        cell["wordBoxesSha256"]=d.digest(cell["wordBoxes"])
        with patch.object(d,"SPECS",specs),self.assertRaisesRegex(ValueError,"independent physical"):
            d.source_tables(pages,"PUSH")

    def test_saved_completion_or_partial_sources_cannot_close_default64(self):
        bad=copy.deepcopy(self.pack)
        bad["complete"]=True
        for pack in (self.pack,bad):
            with self.assertRaises(ValueError):
                d.assess(pack,{"24592":[],"24594":self.fixture["pages"]},self.fixture["entries"],p2.NO_REX)
        self.assertEqual(len(d.SPECS),20)
        self.assertEqual(sum(len(s[3]) for s in d.SPECS.values()),172)


if __name__ == "__main__":
    unittest.main()
