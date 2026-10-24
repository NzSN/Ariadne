"""Independent continuation and wrapped-field source form controls."""
import copy
import unittest
from unittest.mock import patch

import amd64_p2_legacy_media as media


class LegacyMediaControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack=media.entry.read(media.INPUT)
        cls.fixture=media.entry.read(media.INPUT.parent/"p2-legacy-media-source-excerpt.json")

    def check(self,name,record=None,source=None):
        source=self.fixture if source is None else source
        return media.assess_owner(self.pack["owners"][name] if record is None else record,source["pages"],source["entries"])

    def test_x87_continuation_recovers_two_missing_normalized_rows(self):
        result=self.check("FCOM FCOMP FCOMPP")
        self.assertEqual(result["sourceForms"],9)
        table=result["tables"][-1]
        self.assertIsNone(table["header"])
        self.assertEqual(table["continuationOf"],264)
        self.assertEqual([r["selector"] for r in table["rows"]],["FCOMP mem64real","FCOMPP"])
        self.assertEqual([r["sourceEncoding"] for r in table["rows"]],["DC /3","DE D9"])

    def test_wrapped_environment_operands_and_opcodes_have_exact_owned_words(self):
        for name in ("FLDENV","FRSTOR","FSAVE FNSAVE","FSTENV (FNSTENV)"):
            result=self.check(name)
            for row in result["forms"]:
                self.assertIn("mem",row["selector"])
                self.assertTrue(row["sourceEncoding"])
                self.assertIn(row["properties"]["prefix66"],("environment-size-override","environment-size-override-on-no-wait-component"))
                self.assertIn(row["properties"]["environmentBytes"]["operand16"],(14,94))
                self.assertIn(row["properties"]["environmentBytes"]["operand64"],(28,108))

    def test_3dnow_wrapped_opcode_is_not_an_inherited_neighbor_or_new_prefix(self):
        for name,encoding in (("PFACC","0F 0F /r AE"),("PFRCP","0F 0F /r 96")):
            result=self.check(name)
            self.assertEqual(result["forms"][0]["sourceEncoding"],encoding)
            properties=result["forms"][0]["properties"]
            self.assertEqual(properties["prefix66"],"ignored")
            self.assertEqual(properties["family"],"3DNow")
            self.assertFalse(properties["extraPrefixAdmission"])
            self.assertEqual(properties["addressBits"],[64,32])

    def test_byte_count_and_bit_count_are_distinct(self):
        result=self.check("FSTSW (FNSTSW)")
        self.assertEqual(result["forms"][1]["properties"]["explicitMemory"],[dict(value=2,unit="bytes",kind="env")])
        result=self.check("FCOM FCOMP FCOMPP")
        self.assertEqual(result["forms"][2]["properties"]["explicitMemory"],[dict(value=32,unit="bits",kind="real")])
        self.assertEqual(result["forms"][2]["properties"]["prefix66"],"ignored")

    def test_wait_alias_and_macro_component_prefix_ownership_are_distinct(self):
        result=self.check("FWAIT (WAIT)")
        self.assertEqual(result["forms"][0]["properties"]["mnemonicAliases"],["WAIT"])
        self.assertEqual(result["sourceForms"],1)
        result=self.check("FSAVE FNSAVE")
        wait,no_wait=[row["properties"] for row in result["forms"]]
        self.assertEqual(wait["sequenceComponents"],["WAIT","FNSAVE"])
        self.assertEqual(wait["prefix66AppliesTo"],"FNSAVE")
        self.assertIn("does-not-select",wait["prefix66BeforeWait"])
        self.assertEqual(no_wait["prefix66"],"environment-size-override")

    def test_source_form_owner_wrapped_word_and_completion_forgery_fail(self):
        for attack in ("form","operand","opcode","word","owner","prefix","mode","flag"):
            record=copy.deepcopy(self.pack["owners"]["FLDENV"])
            if attack=="form":record["forms"].clear()
            elif attack=="operand":record["forms"][0]["selector"]="FLDENV"
            elif attack=="opcode":record["forms"][0]["sourceEncoding"]="D9 /6"
            elif attack=="word":record["tables"][0]["rows"][0]["selectorWords"].pop()
            elif attack=="owner":record["owner"]="amd-entry:0000"
            elif attack=="prefix":record["forms"][0]["properties"]["prefix66"]="ignored"
            elif attack=="mode":record["forms"][0]["properties"]["addressBits"]=[64]
            else:record["complete"]=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):self.check("FLDENV",record)

    def test_lost_continuation_page_or_complete_source_page_fails(self):
        for number in (264,265,266):
            source=copy.deepcopy(self.fixture)
            source["pages"]=[p for p in source["pages"] if p["pdfPage"]!=number]
            with self.subTest(number=number),self.assertRaises(ValueError):self.check("FCOM FCOMP FCOMPP",source=source)

    def test_independent_physical_scan_detects_an_omission_even_if_expected_list_shrinks(self):
        # Co-deleting a source form from the expected selector list does not
        # hide its actual physical start. It remains outside owned rows.
        specs=copy.deepcopy(media.SPECS)
        ident,first,last,forms=specs["FCOM FCOMP FCOMPP"]
        specs["FCOM FCOMP FCOMPP"]=(ident,first,last,forms[:-1])
        with patch.object(media,"SPECS",specs),self.assertRaises(ValueError):
            media.source_tables(self.fixture["pages"],"FCOM FCOMP FCOMPP")

    def test_shifted_co_omitted_row_is_caught_by_independent_full_column_scan(self):
        specs=copy.deepcopy(media.SPECS)
        ident,first,last,forms=specs["FCOM FCOMP FCOMPP"]
        specs["FCOM FCOMP FCOMPP"]=(ident,first,last,forms[:-1])
        pages=copy.deepcopy(self.fixture["pages"])
        page=next(p for p in pages if p["pdfPage"]==265)
        cell=next(c for c in page["cells"] if c["id"]=="pdf:265:cell:7")
        for word in cell["wordBoxes"]:
            word["rect"][0]+=6
            word["rect"][2]+=6
        cell["wordBoxesSha256"]=media.digest(cell["wordBoxes"])
        with patch.object(media,"SPECS",specs),self.assertRaisesRegex(ValueError,"independent physical"):
            media.source_tables(pages,"FCOM FCOMP FCOMPP")

    def test_partial_fixture_does_not_complete_whole_x87_or_3dnow_population(self):
        with self.assertRaisesRegex(ValueError,"owner denominator"):
            media.assess(self.pack,self.fixture["pages"],self.fixture["entries"],self.fixture["genericPages"])
        self.assertEqual(len(media.SPECS),84)
        self.assertEqual(sum(len(s[3]) for s in media.SPECS.values()),176)


if __name__ == "__main__":
    unittest.main()
