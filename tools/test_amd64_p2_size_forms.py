"""Source form controls for fixed widths, mixed operands and extra-B1 rules."""
import copy
import unittest
from unittest.mock import patch

import amd64_p2_size_forms as s
import amd64_p2_constraints as p2


class SizeExceptionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack=s.entry.read(s.INPUT)
        cls.fixture=s.entry.read(s.INPUT.parent/"p2-size-exception-source-excerpt.json")

    def check(self,owner,record=None,source=None):
        source=self.fixture if source is None else source
        return s.assess_owner(self.pack["owners"][owner] if record is None else record,source["pages"],source["entries"])

    def test_lsl_continuation_recovers_register32_and64_without_widening_selector(self):
        result=self.check("LSL")
        self.assertEqual(result["sourceForms"],3)
        table=result["tables"][-1]
        self.assertIsNone(table["header"])
        self.assertEqual(table["continuationOfHeader"],"pdf:462:cell:50/word:0")
        self.assertEqual([r["selector"] for r in table["rows"]],["LSL reg32, reg/mem16","LSL reg64, reg/mem16"])
        for row,bits in zip(result["forms"],(16,32,64)):
            self.assertEqual(row["properties"]["sourceSelectorBits"],16)
            self.assertEqual(row["properties"]["destinationRegisterBits"],bits)
            self.assertEqual(row["properties"]["computedLimitBits"],32)
            self.assertIn("conditional",row["properties"]["destinationModification"])

    def test_cmpxchg_attribute_width_gpr_component_and_memory_width_are_distinct(self):
        rows=self.check("CMPXCHG8B CMPXCHG16B")["forms"]
        self.assertEqual(rows[0]["properties"]["effectiveAttributeBits"],[16,32])
        self.assertEqual(rows[0]["properties"]["memoryDataBits"],64)
        self.assertEqual(rows[0]["properties"]["gprComponentBits"],32)
        self.assertEqual(rows[1]["sourceEncoding"],"0F C7 /1 m128")
        self.assertEqual(rows[1]["properties"]["effectiveAttributeBits"],[64])
        self.assertEqual(rows[1]["properties"]["memoryDataBits"],128)
        self.assertEqual(rows[1]["properties"]["gprComponentBits"],64)
        self.assertEqual(rows[1]["properties"]["requiredAlignmentBytes"],16)

    def test_bswap_does_not_invent_a_word_form(self):
        rows=self.check("BSWAP")["forms"]
        self.assertEqual([r["properties"]["operandBits"] for r in rows],[32,64])
        self.assertTrue(all(r["properties"]["undefinedOperandBits"]==[16] for r in rows))

    def test_monitor_fixed_implicit_data_is_not_address32_only(self):
        props=self.check("MONITOR")["forms"][0]["properties"]
        self.assertEqual(props["implicitGprBits"],{"ECX":32,"EDX":32})
        self.assertEqual(props["addressBits"],[64,32])
        self.assertEqual(props["addressRegister"],"rAX")
        self.assertIn("not-fixed32",props["addressSelectedBy"])
        self.assertEqual(props["segmentationPagingCheckBytes"],1)
        self.assertIn("not-derived",props["memoryAccessFootprint"])

    def test_selector_store_and_cr0_store_do_not_share_a_source_width_rule(self):
        selector=self.check("SLDT")["forms"]
        status=self.check("SMSW")["forms"]
        self.assertEqual(selector[2]["properties"]["destinationBits"],64)
        self.assertEqual(selector[2]["properties"]["sourceSelectorBits"],16)
        self.assertEqual(status[2]["properties"]["destinationBits"],64)
        self.assertEqual(status[2]["properties"]["cr0SourceBits"],64)
        for rows in (selector,status):
            self.assertEqual(rows[3]["properties"]["destinationKind"],"memory")
            self.assertEqual(rows[3]["properties"]["destinationBits"],16)
            self.assertEqual(rows[3]["properties"]["operandAttributeBits"],[16,32,64])

    def test_rdpid_is_owned_extra_b1_mode_fixed_exception_and_f3_is_not_rep(self):
        row=self.check("RDPID")["forms"][0]
        self.assertEqual(row["sourceEncoding"],"F3 0F C7/7")
        self.assertEqual(row["properties"]["currentDestinationRegisterBits"],64)
        self.assertEqual(row["properties"]["operandWidthSelectedBy"],"execution-mode;not-66-or-REX.W")
        self.assertEqual(row["properties"]["prefixF3"],"opcode-selector;not-repeat")
        self.assertFalse(row["properties"]["extraPrefixAdmission"])
        self.assertIn("not-B1-listed",row["properties"]["kind"])

    def test_mixed_far_pointer_owner_keeps_native_smaller_data_and_address32(self):
        rows=self.check("LDS LES LFS LGS LSS")["forms"]
        self.assertEqual(len(rows),10)
        self.assertEqual(sum(r["properties"]["state"]=="excluded-selected-execution-mode" for r in rows),4)
        for row in rows[4:]:
            props=row["properties"]
            self.assertEqual(props["state"],"native64-source-form")
            self.assertIn(props["offsetBits"],(16,32))
            self.assertEqual(props["memoryPointerBits"],16+props["offsetBits"])
            self.assertEqual(props["addressBits"],[64,32])
            self.assertIn("not-supported",props["operand64"])

    def test_form_mode_feature_clause_and_operand_dimension_forgery_fail(self):
        for attack in ("form","mode","feature","clause","width","prefix","flag"):
            record=copy.deepcopy(self.pack["owners"]["RDPID"])
            props=record["forms"][0]["properties"]
            if attack=="form":record["forms"].clear()
            elif attack=="mode":props["executionModes"]=["compatibility"]
            elif attack=="feature":props["featureRequired"]=None
            elif attack=="clause":record["clauses"]["cells"].pop()
            elif attack=="width":props["currentDestinationRegisterBits"]=32
            elif attack=="prefix":props["prefixF3"]="repeat-count"
            else:record["complete"]=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):self.check("RDPID",record)

    def test_independent_scan_rejects_shifted_co_omitted_lsl64(self):
        specs=copy.deepcopy(s.SPECS)
        ident,first,last,forms=specs["LSL"]
        specs["LSL"]=(ident,first,last,forms[:-1])
        pages=copy.deepcopy(self.fixture["pages"])
        page=next(p for p in pages if p["pdfPage"]==463)
        cell=next(c for c in page["cells"] if c["id"]=="pdf:463:cell:8")
        for word in cell["wordBoxes"]:
            word["rect"][0]+=6
            word["rect"][2]+=6
        cell["wordBoxesSha256"]=s.digest(cell["wordBoxes"])
        with patch.object(s,"SPECS",specs),self.assertRaisesRegex(ValueError,"independent physical"):
            s.source_tables(pages,"LSL")

    def test_partial_source_population_cannot_supply_whole_size_exception_proof(self):
        with self.assertRaises(ValueError):s.assess(self.pack,self.fixture["pages"],self.fixture["entries"],p2.NO_REX)
        self.assertEqual(len(s.SPECS),15)
        self.assertEqual(sum(len(v[3]) for v in s.SPECS.values()),39)


if __name__ == "__main__":
    unittest.main()
