"""Source-backed C closure and preserved source-list discrepancy controls."""
import copy
import contextlib
import io
import unittest
from unittest.mock import patch

import amd64_p2_c as c
import amd64_p2_constraints as p2


class P2CControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = c.entry.read(c.INPUT)
        cls.source = c.entry.read(c.INPUT.parent / "p2-prefix-interpretation-source-excerpt.json")

    def assess(self, pack=None, source=None):
        fixture = self.source if source is None else source
        return c.assess_interpretations(self.pack if pack is None else pack,
                                       fixture["sources"], fixture["normalized"])

    def result(self):
        return dict(boundaryDispositions=[dict(id="p2:"+name, original=copy.deepcopy(p2.BOUNDARIES[name]),
                                               originalSha256=c.digest(p2.BOUNDARIES[name]), state="unresolved")
                                          for name in ("lock-list-disagreement", "repeat-note-disagreement")],
                    referenceDispositions=[dict(original=dict(id=name), currentState="unresolved") for name in c.ROOTS],
                    cellDispositions=[],additionalSections=[],sourceRegions=[])

    def apply(self, result):
        return c.apply_interpretations(result, self.pack, self.source["sources"], self.source["normalized"])

    def test_specific_instruction_and_cross_volume_referral_resolve_scoped_lists(self):
        proof = self.assess()
        self.assertEqual(proof["instructionInventory"]["lockSourceSelectors"], 195)
        self.assertEqual(proof["closedReferences"], ["prefix-note-5"])
        lock = proof["dispositions"]["p2:lock-list-disagreement"]
        self.assertNotIn("CMPXCHG16B", lock["originalVol1Mnemonics"])
        self.assertIn("CMPXCHG16B", lock["originalVol3Mnemonics"])
        self.assertEqual(lock["qualification"]["alignmentBytes"], 16)
        self.assertFalse(lock["publisherCorrection"])
        repeat = proof["dispositions"]["p2:repeat-note-disagreement"]
        self.assertEqual(repeat["countBits"], [64,32])
        self.assertEqual(repeat["countOnly"]["families"], ["INS", "LODS", "MOVS", "OUTS", "STOS"])
        self.assertFalse(repeat["productionAdmission"])

    def test_closure_keeps_original_objects_and_requires_remaining_media_size_roots(self):
        result = self.result()
        originals = {r["id"]:copy.deepcopy(r["original"]) for r in result["boundaryDispositions"]}
        result = self.apply(result)
        for record in result["boundaryDispositions"]:
            self.assertEqual(record["original"], originals[record["id"]])
            self.assertEqual(record["originalSha256"], c.digest(record["original"]))
            self.assertEqual(record["previousDisposition"]["state"], "unresolved")
            self.assertEqual(record["state"], "resolved-source-rule")
        self.assertFalse(result["p2C"]["complete"])
        self.assertEqual(len(result["p2C"]["remainingReferences"]),4)
        self.assertIn("prefix-note-6",result["p2C"]["remainingReferences"])

    def test_saved_completion_flags_and_reference_promotions_do_not_complete_c(self):
        result = self.result()
        result["p2C"] = dict(complete=True,remainingReferences=[])
        for record in result["referenceDispositions"]:
            record["currentState"] = "resolved-source-rule"
            record["cProof"] = dict(check="forged",complete=True)
            record["rules"] = ["forged"]
        self.assertFalse(self.apply(result)["p2C"]["complete"])
        self.assertEqual(len(result["p2C"]["remainingReferences"]),4)
        self.assertEqual(result["remainingArchitecturalReferences"],result["p2C"]["remainingReferences"])
        self.assertEqual(p2.incomplete_obligations(result)["references"],4)
        for record in result["referenceDispositions"]:
            if record["original"]["id"]!="prefix-note-5":
                self.assertEqual(record["currentState"],"unresolved")
                self.assertNotIn("cProof",record)
                self.assertEqual(record["rules"],[])

    def test_unimplemented_reference_cannot_close_by_adding_a_saved_proof_flag(self):
        with self.assertRaisesRegex(ValueError,"recipe"):
            c.derive_c_status(self.result(),{"operand-note-2":dict(check="saved-complete",complete=True)})

    def test_c_gate_is_independent_of_full_p2_saved_flags(self):
        result=dict(typedClauses=31,sourceAnchors=810,cellCounts={},remainingArchitecturalReferences=[],
                    additionalSections=[],p2Complete=True,p2C=dict(complete=False,remainingReferences=list(c.ROOTS)))
        args=["amd64_p2_constraints.py","extract","--old-cache","old","--publisher-cache","publisher",
              "--baseline-root","baselines","--output","fresh","--require-c-complete"]
        with patch("sys.argv",args),patch.object(p2,"reconstruct",return_value=result) as reconstruct,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as failure:p2.main()
        self.assertEqual(failure.exception.code,2)
        reconstruct.assert_called_once()

    def test_omitted_owner_row_or_source_clause_cannot_close_reference(self):
        for attack in ("owner", "row", "page", "literal", "geometry"):
            source = copy.deepcopy(self.source)
            if attack == "owner": source["normalized"]["entries"].pop()
            elif attack == "row": source["normalized"]["rows"].pop()
            elif attack == "page": source["sources"]["24592"] = []
            else:
                page = next(p for p in source["sources"]["24594"] if p["pdfPage"] == 211)
                cell = next(v for v in page["cells"] if v["id"] == "pdf:211:cell:18")
                if attack == "literal": cell["text"] = "No LOCK support"
                else: cell["wordBoxes"][0]["rect"][0] += 1
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                self.assess(source=source)

    def test_scope_rule_anchor_feature_and_saved_resolution_forgery_fail(self):
        for attack in ("scope", "feature", "anchor", "list", "flags", "prefix", "counter"):
            pack=copy.deepcopy(self.pack)
            if attack == "scope": pack["executionModes"] = ["long-mode"]
            elif attack == "anchor": pack["anchors"]["cmpxchg-wide-lock"]["clause"]["cells"].pop()
            elif attack == "list": pack["interpretations"]["p2:lock-list-disagreement"]["originalVol1Mnemonics"].append("CMPXCHG16B")
            elif attack == "feature": pack["interpretations"]["p2:lock-list-disagreement"]["qualification"]["feature"] = None
            elif attack == "prefix": pack["interpretations"]["p2:repeat-note-disagreement"]["countOnly"]["prefix"] = "f2"
            elif attack == "counter": pack["interpretations"]["p2:repeat-note-disagreement"]["countBits"] = [64]
            else: pack["complete"] = True
            with self.subTest(attack=attack), self.assertRaises(ValueError): self.assess(pack=pack)


class SizeReferencePartitionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack=c.entry.read(c.PARTITION_INPUT)
        cls.references=[dict(original=c.original_architecture_reference(name),
                             originalSha256=c.digest(c.original_architecture_reference(name)),currentState="unresolved")
                        for name in cls.pack["originalReferencesSha256"]]
        # This class tests the reference partition only. Public apply_all
        # reconstructs the full default64 proof before calling this function.
        cls.default=dict(state="checked-default64-operand-attribute-subproof",sourceForms=172,
                         normalOperandAttributeScope=dict(sourceCells=cls.pack["coveredRequirement"]["sourceCells"]),
                         b5Groups={name:[] for name,_,_ in c.default64.native.B5},globalDefaultFixedCensusComplete=False)
        source=c.entry.read(c.size_forms.INPUT.parent/"p2-size-exception-source-excerpt.json")
        pack=c.entry.read(c.size_forms.INPUT)
        rdpid=c.size_forms.assess_owner(pack["owners"]["RDPID"],source["pages"],source["entries"])
        cls.exceptions=dict(owners={"RDPID":rdpid})

    def assess(self,pack=None,references=None,default=None,exceptions=None):
        return c.assess_size_partition(self.pack if pack is None else pack,self.references if references is None else references,
            self.default if default is None else default,self.exceptions if exceptions is None else exceptions)

    def test_broad_pointer_remains_owned_and_census_is_not_promoted(self):
        proof=self.assess()
        self.assertEqual(proof["openSuccessorReferences"],["operand-note-2","prefix-note-2"])
        self.assertFalse(proof["globalDefaultFixedCensusComplete"])
        self.assertFalse(proof["wholeCComplete"])
        root=next(r["original"] for r in self.references if r["original"]["id"]=="default64-instruction-exceptions")
        covered=self.pack["coveredRequirement"]["sourceCells"]
        shared=self.pack["sharedRequirements"][0]["sourceCells"]
        located=self.pack["locatedReference"]["sourceCells"]
        self.assertEqual(set(covered+shared+located),set(root["sourceCells"]))
        self.assertEqual(len(covered+shared+located),len(set(root["sourceCells"])))

    def test_partition_cannot_drop_move_or_globally_close_shared_requirements(self):
        for attack in ("drop","owner","scope","source","flag"):
            pack=copy.deepcopy(self.pack)
            if attack=="drop":pack["sharedRequirements"].pop()
            elif attack=="owner":pack["sharedRequirements"][0]["owner"]="prefix-note-6"
            elif attack=="scope":pack["coveredRequirement"]["domain"]="all-native64-fixed-size-instructions"
            elif attack=="source":pack["coveredRequirement"]["sourceCells"].pop()
            else:pack["globalDefaultFixedCensusComplete"]=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):self.assess(pack=pack)
        refs=copy.deepcopy(self.references)
        refs[0]["original"]["sourceCells"].pop()
        with self.assertRaises(ValueError):self.assess(references=refs)

    def test_rdpid_cannot_be_erased_or_recast_as_an_ordinary_size_override(self):
        exceptions=copy.deepcopy(self.exceptions)
        exceptions["owners"]["RDPID"]["forms"][0]["properties"]["operandWidthSelectedBy"]="REX.W"
        with self.assertRaises(ValueError):self.assess(exceptions=exceptions)
        default=copy.deepcopy(self.default)
        default["globalDefaultFixedCensusComplete"]=True
        with self.assertRaises(ValueError):self.assess(default=default)


class WholeModeOwnerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack=c.entry.read(c.MODE_INPUT)
        cls.fixture=c.entry.read(c.MODE_INPUT.parent/"p2-native64-owner-source-excerpt.json")
        native_fixture=c.entry.read(c.prefixes.native.INPUT.parent/"p2-native64-source-excerpt.json")
        cls.mode_pages={p["pdfPage"]:p for p in native_fixture["pages"]}
        cls.tables={name:c.prefixes.native.parse_mode_table(cls.mode_pages[spec[0]],name)
                    for name,spec in c.prefixes.native.MODE_TABLES.items()}

    def check(self,name,record=None,source=None):
        source=self.fixture if source is None else source
        return c.assess_mode_owner(name,self.pack["owners"][name] if record is None else record,
                                   source["pages"],source["normalized"],self.tables)

    def test_reassigned_old_owners_do_not_exclude_evex_or_movsxd(self):
        for name,forms in (("BOUND",2),("ARPL",1)):
            result=self.check(name)
            self.assertEqual(result["sourceForms"],forms)
            self.assertEqual(result["state"],"excluded-selected-execution-mode")
            self.assertFalse(result["replacementEncodingOwnersExcluded"])
            self.assertIn("not-leading-byte-exclusion",result["scope"])
            self.assertEqual(result["modeTable"],"reassigned64")

    def test_owned_system_clauses_exclude_sysenter_sysexit_but_not_sysret(self):
        for name in ("SYSENTER","SYSEXIT"):
            result=self.check(name)
            self.assertEqual(result["modeTable"],"invalidLongMode")
            self.assertEqual(result["sourceForms"],1)
        self.assertNotIn("SYSRET",c.WHOLE_MODE_OWNERS)
        self.assertEqual(len(c.WHOLE_MODE_OWNERS),13)

    def test_mixed_owners_cannot_be_promoted_from_some_excluded_rows(self):
        for name in ("CALL (Far)","JMP (Far)","LDS LES LFS LGS LSS","INC","DEC","POP","PUSH","MOVD"):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,"complete owner"):
                c.assess_mode_owner(name,{},[],{},self.tables)

    def test_owner_row_omission_and_scope_forgery_fail(self):
        for attack in ("owner","row","clause","table","flag"):
            record=copy.deepcopy(self.pack["owners"]["BOUND"])
            source=copy.deepcopy(self.fixture)
            if attack=="owner":record["owner"]="amd-entry:0089"
            elif attack=="row":source["normalized"]["rows"]=[r for r in source["normalized"]["rows"] if r["mnemonic"]!="BOUND reg32, mem32&mem32"]
            elif attack=="clause":record["clause"]["cells"].pop()
            elif attack=="table":record["modeTable"]="invalidLongMode"
            else:record["excluded"]=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):self.check("BOUND",record,source)

    def test_partial_sources_and_compatibility_scope_cannot_supply_whole_proof(self):
        pages=self.fixture["pages"]+[self.mode_pages[i] for i in (653,654)]
        for attack in ("partial","scope","omitted-owner"):
            pack=copy.deepcopy(self.pack)
            if attack=="scope":pack["executionModes"]=["compatibility"]
            elif attack=="omitted-owner":pack["owners"].pop("AAA")
            with self.subTest(attack=attack),self.assertRaises(ValueError):
                c.assess_mode_exclusions(pack,pages,self.fixture["normalized"])


if __name__ == "__main__":
    unittest.main()
