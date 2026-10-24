"""Controls for source identity, literal contradictions and scoped comparisons."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import amd64_paired_constraints as source


class PairedSourceControls(unittest.TestCase):
    def setUp(self):
        self.pack = source.entry.read(source.INPUT)

    def test_reviewed_pack_keeps_both_revisions_and_all_three_families(self):
        source.validate_structure(self.pack)
        self.assertEqual(set(self.pack["owners"]), {"gf","movd","fma"})
        self.assertEqual(len(self.pack["clauses"]), 24)
        self.assertEqual(sum(map(len,self.pack["sourceCells"].values())), 328)
        self.assertNotEqual(self.pack["sources"]["predecessor"], self.pack["sources"]["replacement"])

    def test_rule_and_boundary_removal_parameter_forgery_and_type_forgery_fail(self):
        for attack in ("rule","boundary","parameter","boolean-type","text-relation"):
            pack = copy.deepcopy(self.pack)
            if attack == "rule": pack["clauses"].pop("movd-mode-notes")
            elif attack == "boundary": pack["boundaries"].pop("fma-w")
            elif attack == "parameter": pack["clauses"]["fma-clear-prose"]["parameters"]["clearRanges"][1][1] = 511
            elif attack == "boolean-type": pack["clauses"]["gf-mask"]["parameters"]["memoryFaultSuppression"] = 0
            else: pack["clauses"]["gf-heading"]["selectedTextEqual"] = True
            with self.subTest(attack=attack), self.assertRaises(ValueError): source.validate_structure(pack)

    def test_swapped_sides_owner_extent_and_pins_fail(self):
        for attack in ("sides","owner","extent","publisher","entry-pin","admission"):
            pack = copy.deepcopy(self.pack)
            if attack == "sides": pack["sourceCells"]["replacement"] = pack["sourceCells"]["predecessor"]
            elif attack == "owner": pack["owners"]["gf"] = pack["owners"]["movd"]
            elif attack == "extent": pack["owners"]["fma"]["new"]["pdfEndPage"] += 1
            elif attack == "publisher": pack["sources"]["replacement"] = "0"*64
            elif attack == "entry-pin": pack["entryReviewInput"]["sha256"] = "0"*64
            else: pack["productionAdmission"] = True
            with self.subTest(attack=attack), self.assertRaises(ValueError): source.validate_structure(pack)

    def test_missing_extra_and_relabelled_anchor_fail(self):
        for attack in ("missing","extra","identity","fields"):
            pack = copy.deepcopy(self.pack)
            anchors = pack["sourceCells"]["replacement"]
            key = next(iter(anchors))
            if attack == "missing": anchors.pop(key)
            elif attack == "extra": anchors["foreign"] = copy.deepcopy(anchors[key])
            elif attack == "identity": anchors[key]["id"] = "foreign"
            else: anchors[key]["text"] = "forged passing source"
            with self.subTest(attack=attack), self.assertRaises(ValueError): source.validate_structure(pack)

    def headings(self):
        actual = {}
        for side,identifier,text in (
            ("predecessor","pdf:226:cell:315","HADDPD, VHADDPD"),
            ("replacement","pdf:228:cell:299","GF2P8AFFINEINVQB VGF2P8AFFINEINVQB"),
        ):
            expected = self.pack["sourceCells"][side][identifier]
            actual[side] = {identifier:{**copy.deepcopy(expected),"text":text}}
        return actual

    def test_actual_heading_repair_remains_a_text_difference(self):
        actual = self.headings()
        for side,anchors in actual.items():
            for identifier,cell in anchors.items():
                source.conversion.validate_anchor(self.pack["sourceCells"][side][identifier],cell)
        observation = source.clause_observation(self.pack,"gf-heading",actual)
        self.assertFalse(observation["selectedTextEqual"])
        self.assertNotEqual(*observation["textSha256"].values())

    def test_erasing_changed_heading_or_moving_it_to_another_owner_fails(self):
        actual = self.headings()
        actual["replacement"]["pdf:228:cell:299"]["text"] = "HADDPD, VHADDPD"
        with self.assertRaisesRegex(ValueError,"text relation"):
            source.clause_observation(self.pack,"gf-heading",actual)
        actual = self.headings()
        actual["replacement"]["pdf:228:cell:299"]["pdfPage"] = 341
        with self.assertRaisesRegex(ValueError,"escapes owner"):
            source.clause_observation(self.pack,"gf-heading",actual)

    def test_actual_scalar_clear_statement_is_preserved_literally(self):
        texts = [
            "The destination is an XMM register. When the result is written to the destination XMM register, bits",
            "[127:32] of the destination and bits [512:128] of the corresponding YMM/ZMM register are cleared.",
        ]
        actual = {}
        for side,page in (("predecessor",1043),("replacement",1173)):
            actual[side] = {}
            for ordinal,text in zip((41,42),texts):
                identifier = f"pdf:{page}:cell:{ordinal}"
                expected = self.pack["sourceCells"][side][identifier]
                cell = {**copy.deepcopy(expected),"text":text}
                source.conversion.validate_anchor(expected,cell)
                actual[side][identifier] = cell
        self.assertTrue(source.clause_observation(self.pack,"fma-clear-prose",actual)["selectedTextEqual"])
        actual["replacement"]["pdf:1173:cell:42"]["text"] = texts[1].replace("512", "511")
        with self.assertRaisesRegex(ValueError,"source terms"):
            source.clause_observation(self.pack,"fma-clear-prose",actual)

    def test_actual_anchor_text_geometry_and_word_identity_cannot_drift(self):
        identifier = "pdf:228:cell:299"
        expected = self.pack["sourceCells"]["replacement"][identifier]
        original = self.headings()["replacement"][identifier]
        for field in ("text","pdfPage","rect","wordSpan","wordBoxesSha256","unicodeSha256"):
            changed = copy.deepcopy(original)
            if field in ("rect","wordSpan"): changed[field][0] += 1
            elif field == "pdfPage": changed[field] += 1
            else: changed[field] = "forged"
            with self.subTest(field=field), self.assertRaises(ValueError):
                source.conversion.validate_anchor(expected,changed)

    def test_missing_actual_geometry_and_duplicate_cells_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"omitted/duplicate"):
            source.validate_cells(self.pack,dict(predecessor=[],replacement=[]))
        cell = self.headings()["predecessor"]["pdf:226:cell:315"]
        with self.assertRaisesRegex(ValueError,"omitted/duplicate"):
            source.validate_cells(self.pack,dict(predecessor=[dict(cells=[cell,copy.deepcopy(cell)])],replacement=[]))

    def test_conflicts_remain_source_claims_without_corrections(self):
        self.assertEqual(self.pack["clauses"]["movd-non64-vex-store-row"]["parameters"]["literalOpcode"], "6E /r")
        self.assertEqual(self.pack["clauses"]["movd-64-vex-store-row"]["parameters"]["literalOpcode"], "7E /r")
        self.assertEqual(self.pack["clauses"]["fma-three-operand-w-prose"]["parameters"]["declaredW"], 1)
        self.assertEqual(self.pack["clauses"]["fma-evex-rows"]["parameters"]["literalW"], 0)
        self.assertEqual(sum(b["kind"] == "source-conflict" for b in self.pack["boundaries"].values()),4)

    def test_maintained_output_and_missing_previous_products_do_not_qualify_source(self):
        with self.assertRaisesRegex(ValueError,"test output must"):
            source.reconstruct(Path("old"),Path("new"),source.INPUT.parent/"generated")
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError,"missing"):
            source.check(Path("old"),Path("new"),Path(tmp)/"missing")

    def test_reconstruction_must_replay_preceding_conversion_and_all_pdfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(source.conversion,"reconstruct",side_effect=ValueError("missing pinned runtime")) as replay:
                with self.assertRaisesRegex(ValueError,"missing pinned runtime"):
                    source.reconstruct(Path("old"),Path("new"),Path(tmp)/"fresh")
                replay.assert_called_once()
                self.assertFalse((Path(tmp)/"fresh/paired-constraints.json").exists())


if __name__ == "__main__":
    unittest.main()
