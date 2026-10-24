"""Actual source inputs prevent an opcode-table disagreement being hidden."""
import copy
import unittest

import amd64_p2_media as media
import amd64_p2_constraints as p2


class MediaPrefixQuestionControls(unittest.TestCase):
    def setUp(self):
        self.pack = media.entry.read(media.INPUT)
        self.pages = media.entry.read(media.INPUT.parent / "p2-media-prefix-source-excerpt.json")

    def test_old_and_selected_instruction_literals_conflict_with_map(self):
        result = media.assess(self.pack, self.pages)
        self.assertEqual(result["state"], "unresolved-source-interpretation")
        self.assertEqual(result["observations"]["old-encoding"]["text"], "66 0F 57 /r")
        self.assertEqual(result["observations"]["encoding"]["text"], "66 0F 57 /r")
        self.assertEqual(result["observations"]["map-none"]["text"], "none")
        self.assertFalse(result["sourceCorrection"])
        self.assertFalse(result["prefixAdmission"])

    def test_scope_identity_omission_and_saved_resolution_fail(self):
        for attack in ("mode", "pin", "omission", "resolution"):
            pack = copy.deepcopy(self.pack)
            if attack == "mode": pack["executionModes"] = ["host-64"]
            elif attack == "pin": pack["pages"]["xorps"]["pdfSha256"] = "0"*64
            elif attack == "omission": del pack["pages"]["old-xorps"]
            else: pack["resolved"] = True
            with self.subTest(attack=attack), self.assertRaises(ValueError): media.assess(pack, self.pages)

    def test_source_literal_and_map_row_column_mutations_fail(self):
        for attack in ("opcode", "row", "column"):
            pages, pack = copy.deepcopy(self.pages), copy.deepcopy(self.pack)
            if attack == "opcode":
                pages["xorps"]["cells"][7]["text"] = "0F 57 /r"
            else:
                page = pages["map"]
                cell = next(c for c in page["cells"] if c["id"] == "pdf:571:cell:117")
                axis = 1 if attack == "row" else 0
                cell["rect"][axis] -= 44
                cell["rect"][axis+2] -= 44
                # A forged page digest cannot turn a wrong geometric owner
                # into proof of the source table's actual prefix band.
                pack["pages"]["map"]["cellsSha256"] = media.digest(page["cells"])
            with self.subTest(attack=attack), self.assertRaises(ValueError): media.assess(pack, pages)

    def test_strict_gate_counts_new_questions_even_when_old_categories_close(self):
        result = dict(cellDispositions=[], referenceDispositions=[], boundaryDispositions=[],
                      additionalSections=[], sourceRegions=[], p2Complete=True,
                      cSourceQuestions=[dict(state="unresolved-source-interpretation")])
        self.assertEqual(p2.incomplete_obligations(result)["boundaries"], 1)

    def test_selected_vol3_rule_preserves_original_literals_and_source_question(self):
        choice = media.entry.read(media.PRECEDENCE_INPUT)
        original = media.assess(self.pack, self.pages)
        current = media.project_current_scope(self.pack, self.pages, choice)
        self.assertEqual(current["state"], "resolved-source-rule")
        self.assertEqual(current["id"], original["id"])
        self.assertEqual(current["originalAssessment"], original)
        self.assertEqual(current["originalAssessmentSha256"], media.digest(original))
        self.assertEqual(current["originalAssessment"]["observations"]["encoding"]["text"], "66 0F 57 /r")
        self.assertEqual([(f["selector"], f["mandatoryPrefix"]) for f in current["currentForms"]],
                         [("XORPS xmm1, xmm2/mem128", None), ("XORPD xmm1, xmm2/mem128", "66")])
        self.assertTrue(all(f["dataBits"] == 128 for f in current["currentForms"]))
        self.assertFalse(current["sourceCorrection"])
        self.assertFalse(current["prefixAdmission"])
        self.assertFalse(current["productionAdmission"])

    def test_precedence_cannot_widen_to_other_modes_forms_or_conflicts(self):
        for attack in ("mode", "authority", "page", "owner", "prefix", "width", "scope", "vex", "runtime", "raw-input", "saved-state"):
            choice = media.entry.read(media.PRECEDENCE_INPUT)
            if attack == "mode": choice["executionModes"] = ["long-compatibility"]
            elif attack == "authority": choice["authority"]["publication"] = "26568"
            elif attack == "page": choice["authority"]["pdfPage"] = 655
            elif attack == "owner": choice["forms"][0]["selector"] = "PXOR mmx1, mmx2/mem64"
            elif attack == "prefix": choice["forms"][0]["mandatoryPrefix"] = "66"
            elif attack == "width": choice["forms"][1]["dataBits"] = 16
            elif attack == "scope": choice["question"] = "paired:gf-inverse-table"
            elif attack == "vex": choice["limits"]["vexEvex"] = "all-forms-selected"
            elif attack == "runtime": choice["limits"]["productionAdmission"] = True
            elif attack == "raw-input": choice["questionInputSha256"] = "0"*64
            else: choice["state"] = "resolved-source-rule"
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                media.project_current_scope(self.pack, self.pages, choice)

    def test_source_reconstruction_remains_required_after_selection(self):
        choice = media.entry.read(media.PRECEDENCE_INPUT)
        bad = copy.deepcopy(self.pages)
        bad["xorps"]["cells"][7]["text"] = "0F 57 /r"
        with self.assertRaises(ValueError): media.project_current_scope(self.pack, bad, choice)
        with self.assertRaises(ValueError): media.project_current_scope(self.pack, {}, choice)

    def test_selection_closes_only_its_additive_question(self):
        current = media.project_current_scope(self.pack, self.pages, media.entry.read(media.PRECEDENCE_INPUT))
        result = dict(cellDispositions=[dict(currentState="source-conflict")],
                      referenceDispositions=[dict(currentState="unresolved")],
                      boundaryDispositions=[dict(id="p2:other", state="unresolved"), dict(id="paired:gf-inverse-table",state="unresolved")],
                      additionalSections=[dict(state="required-clause-review")],
                      sourceRegions=[dict(state="required-whole-region-clause-review")], cSourceQuestions=[current])
        self.assertEqual(p2.incomplete_obligations(result), dict(cells=1,references=1,boundaries=1,inheritedBoundaries=1,addedSections=1,regions=1))

    def test_all_twelve_owned_source_rows_keep_their_distinct_prefix_fields(self):
        result = media.assess_xor_forms(media.entry.read(media.XOR_FORMS_INPUT), self.pages,
                                        media.entry.read(media.PRECEDENCE_INPUT))
        self.assertEqual((result["legacyRows"],result["vexRows"],result["evexRows"]), (2,4,6))
        for row in result["rows"]:
            p = row["properties"]
            if p["encoding"] == "legacy":
                self.assertEqual(row["sourceEncoding"], "66 0F 57 /r")
                self.assertEqual(p["mandatoryPrefix"], None if p["family"] == "XORPS" else "66")
                self.assertEqual(p["vectorBits"],128)
            else:
                self.assertIsNone(p["mandatoryPrefix"])
                self.assertEqual(p["embeddedPp"], "00" if p["family"] == "XORPS" else "01")
            if p["encoding"] == "EVEX":
                self.assertEqual(p["broadcastElementBits"],32 if p["family"] == "XORPS" else 64)
        self.assertFalse(result["wholePrefixInventoryComplete"])
        self.assertFalse(result["legalDomainsComplete"])
        self.assertFalse(result["productionAdmission"])

    def test_source_row_omission_duplicate_wrong_owner_and_prefix_conflation_fail(self):
        for attack in ("omit", "duplicate", "owner", "shared-fields", "word-operand", "pp", "W", "L", "LL", "broadcast", "strip-raw", "extra-prefix", "scope"):
            pack = media.entry.read(media.XOR_FORMS_INPUT)
            if attack == "omit": pack["rows"].pop()
            elif attack == "duplicate": pack["rows"][-1] = copy.deepcopy(pack["rows"][-2])
            elif attack == "owner": pack["rows"][1]["selector"] = pack["rows"][7]["selector"]
            elif attack == "shared-fields": pack["rows"][1]["encodingCells"] = pack["rows"][2]["encodingCells"]
            elif attack == "word-operand": pack["rows"][0]["properties"]["vectorBits"] = 16
            elif attack == "pp": pack["rows"][1]["properties"]["embeddedPp"] = "01"
            elif attack == "W": pack["rows"][3]["properties"]["W"] = 1
            elif attack == "L": pack["rows"][2]["properties"]["L"] = 0
            elif attack == "LL": pack["rows"][5]["properties"]["LL"] = "00"
            elif attack == "broadcast": pack["rows"][3]["properties"]["broadcastElementBits"] = 64
            elif attack == "strip-raw": pack["rows"][0]["sourceEncoding"] = "0F 57 /r"
            elif attack == "extra-prefix": pack["rows"][1]["properties"]["mandatoryPrefix"] = "66"
            else: pack["wholePrefixInventoryComplete"] = True
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                media.assess_xor_forms(pack,self.pages,media.entry.read(media.PRECEDENCE_INPUT))

    def test_other_xor_forms_are_not_inferred_from_a_passing_selected_row(self):
        for args in (("PXOR","legacy",128),("XORPS","VEX",512),("XORPD","legacy",16),("XORPS","EVEX",64)):
            with self.subTest(args=args), self.assertRaises(ValueError): media.xor_form_contract(*args)


if __name__ == "__main__":
    unittest.main()
