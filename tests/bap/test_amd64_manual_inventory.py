"""Source-row accounting controls, independent of the large downloaded manuals."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import amd64_manual_inventory as manual

CHAPTER = "3 General-Purpose Instruction Reference"
HEADER = f"{'Mnemonic':<32}{'Opcode':<16}Description"


def line(name="", code="", description=""):
    return f"{name:<32}{code:<16}{description}"


def outline(entries=None, pages=1):
    entries = entries or [dict(title="CMOVcc", uri="#CMOVcc", pdfPage=1)]
    return dict(pages=pages, outline=[dict(title=CHAPTER, pdfPage=1, children=entries),
                                      dict(title="Appendix", pdfPage=pages + 1)])


def fixture():
    text = "\n".join([HEADER, line("CMOVB reg16, reg/mem16"),
                       line("CMOVB reg32, reg/mem32", "0F 42 /r", "Move if below."),
                       line("CMOVB reg64, reg/mem64"), "Related Instructions", "CMP"])
    return manual.extract(text, outline(), [CHAPTER])


def publication():
    content = fixture()
    comparison = dict(xedRecordsSha256="e" * 64, rows=[])
    result = dict(schema=manual.SCHEMA, publication="24594", revision="test",
                  sourceProvenance={"officialByteIdentity": "not-independently-verified"},
                  pdfSha256="a" * 64, layoutTextSha256="b" * 64, outlineSha256="c" * 64,
                  scope={"unit": "physical source row"}, content=content,
                  contentSha256=manual.digest(content), counts=manual.counts(content),
                  xedComparison=comparison)
    pin = {key: result[key] for key in ("publication", "revision", "sourceProvenance", "pdfSha256",
                                       "layoutTextSha256", "outlineSha256", "contentSha256", "counts")}
    pin.update(scopeSha256=manual.digest(result["scope"]), xedRecordsSha256="e" * 64,
               xedComparisonSha256=manual.digest(comparison))
    return result, pin


class ManualInventoryControls(unittest.TestCase):
    def test_shared_opcode_cells_are_gaps_not_silently_filled_down(self):
        content = fixture()
        self.assertEqual(len(content["rows"]), 3)
        self.assertEqual([row["encodingCells"] for row in content["rows"]], [[], ["0F 42 /r"], []])
        self.assertEqual(manual.counts(content)["gaps"], {"missing-or-merged-encoding-cell": 2})

    def test_every_table_line_is_accounted_and_unknown_text_survives(self):
        text = "\n".join([HEADER, "", line("CMOVB reg32, reg/mem32", "0F 42 /r"),
                           "unknown layout construct", "Related Instructions"])
        content = manual.extract(text, outline(), [CHAPTER])
        self.assertEqual(len(content["tables"][0]["lines"]), 3)
        self.assertEqual(content["gaps"][0]["kind"], "unparsed-table-line")
        self.assertEqual(content["gaps"][0]["sourceText"], "unknown layout construct")
        self.assertEqual(content["gaps"][0]["source"]["line"], 4)

    def test_description_does_not_become_opcode_and_prose_does_not_become_row(self):
        text = "\n".join([HEADER, line("CMOVB reg16, reg/mem16", "", "Move if below."),
                           "For details about control transfers", "Related Instructions"])
        content = manual.extract(text, outline(), [CHAPTER])
        self.assertEqual(len(content["rows"]), 1)
        self.assertEqual(content["rows"][0]["encodingCells"], [])
        self.assertIn("unparsed-table-line", manual.counts(content)["gaps"])

    def test_single_letter_condition_family_and_far_alias_remain_candidates(self):
        self.assertTrue(manual.mnemonic_belongs("JAE", ["Jcc"]))
        self.assertTrue(manual.mnemonic_belongs("RETF", ["RET (Far)"]))
        self.assertFalse(manual.mnemonic_belongs("XMM0", ["ADDPS VADDPS"]))

    def test_centered_header_does_not_truncate_a_left_aligned_opcode(self):
        header = "       Mnemonic                  Opcode                         Description"
        data = "       MONITORX                 0F 01 FA            Establishes a range to be monitored"
        kind, row = manual.classify_table_line(data, header)
        self.assertEqual(kind, "row")
        self.assertEqual(row["mnemonic"], "MONITORX")
        self.assertEqual(row["encodingCells"], ["0F 01 FA"])

    def test_wrapped_operand_keeps_its_source_anchor(self):
        text = "\n".join([HEADER, line("IMUL reg16, reg/mem16,", "69 /r iw"),
                           line("imm16", "", "The immediate operand."), "Related Instructions"])
        index = outline([dict(title="IMUL", uri="#IMUL", pdfPage=1)])
        content = manual.extract(text, index, [CHAPTER])
        self.assertEqual(content["rows"][0]["mnemonic"], "IMUL reg16, reg/mem16, imm16")
        self.assertEqual(content["rows"][0]["sourceContinuations"][0]["line"], 3)
        self.assertEqual(manual.counts(content)["lineClasses"]["operand-continuation"], 1)

    def test_same_page_alias_entries_and_subsections_remain_in_index(self):
        entries = [dict(title="XLAT", uri="#one", pdfPage=1),
                   dict(title="XLATB", uri="#two", pdfPage=1, children=[dict(title="Detail", pdfPage=1)])]
        result = manual.entries_from_outline(outline(entries), [CHAPTER])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["pdfEndPage"], 1)
        self.assertEqual(result[1]["subsections"][0]["title"], "Detail")
        content = manual.extract(HEADER + "\n" + line("XLATB", "D7") + "\nRelated Instructions",
                                 outline(entries), [CHAPTER])
        self.assertEqual(content["rows"][0]["entryIds"], ["amd-entry:0000", "amd-entry:0001"])

    def test_reference_only_alias_is_recorded_without_fabricating_rows(self):
        index = outline([dict(title="SHL", uri="#SHL", pdfPage=1)])
        content = manual.extract("This instruction is synonymous with the SAL instruction.", index, [CHAPTER])
        self.assertEqual(content["entries"][0]["explicitAliasOf"], "SAL")
        self.assertEqual(content["rows"], [])
        self.assertEqual(content["gaps"], [])

    def test_constraints_have_page_line_hash_and_preserve_unformalized_statement(self):
        text = "In 64-bit mode, VEX.W selects the operand size.\nCPUID Fn0000_0007_EBX[BMI1] = 1.\n"
        content = manual.extract(text, outline(), [CHAPTER])
        refs = content["constraintReferences"]
        self.assertIn("mode", refs[0]["categories"])
        self.assertIn("prefix", refs[0]["categories"])
        self.assertIn("feature", refs[1]["categories"])
        self.assertEqual(refs[1]["pdfPage"], 1)
        self.assertEqual(refs[1]["line"], 2)
        self.assertEqual(len(refs[1]["textSha256"]), 64)

    def test_xed_name_and_encoding_text_matches_remain_candidates(self):
        rows = [dict(id="one", mnemonic="SETC reg8", encodingCells=["0F 92 /r"]),
                dict(id="two", mnemonic="SETB reg8", encodingCells=["0F 92 /r"])]
        comparison = manual.reconcile(rows, {"records": [{"id": "xed:b", "mnemonic": "SETB"}]})
        self.assertEqual(comparison[0]["relation"], "unmatched-name")
        self.assertEqual(comparison[0]["sameEncodingTextNameCandidates"], ["SETB"])
        self.assertEqual(comparison[1]["exactNameCandidates"], ["xed:b"])
        self.assertFalse(any(row["encodingLegalityReconciled"] for row in comparison))

    def test_frozen_pin_detects_omitted_rows_gaps_or_changed_comparison_and_provenance(self):
        good, pin = publication()
        manual.validate_output(good, pin)
        for key in ("rows", "gaps", "entries", "tables"):
            changed = copy.deepcopy(good)
            changed["content"][key] = []
            changed["contentSha256"] = manual.digest(changed["content"])
            changed["counts"] = manual.counts(changed["content"])
            with self.assertRaises(ValueError):
                manual.validate_output(changed, pin)
        changed = copy.deepcopy(good)
        changed["xedComparison"]["rows"] = [{"encodingLegalityReconciled": True}]
        with self.assertRaises(ValueError):
            manual.validate_output(changed, pin)
        changed = copy.deepcopy(good)
        changed["sourceProvenance"]["officialByteIdentity"] = "verified"
        with self.assertRaises(ValueError):
            manual.validate_output(changed, pin)

    def test_page_count_and_chapter_boundary_changes_are_rejected(self):
        with self.assertRaises(ValueError):
            manual.extract("one\fextra", outline(), [CHAPTER])
        with self.assertRaises(ValueError):
            manual.entries_from_outline(outline(), ["missing chapter"])
        with self.assertRaises(ValueError):
            manual.entries_from_outline(outline([dict(title="CMOVcc", uri="#bad", pdfPage=0)]), [CHAPTER])

    def test_exact_transcription_gate_cannot_promote_retained_gaps(self):
        result, _ = publication()
        with self.assertRaisesRegex(ValueError, "source transcription is incomplete"):
            manual.require_no_gaps(result)


if __name__ == "__main__":
    unittest.main()
