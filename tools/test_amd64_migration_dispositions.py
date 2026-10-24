"""Original migration identities and derived acceptance facets stay separate."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import amd64_migration_dispositions as source


def inputs():
    reviewed = source.entry.read(source.entry.INPUT)
    entries = []
    for link in reviewed["pairedFamilies"]:
        entries.extend([(direction, link[side]) for side, direction in (("old", "removed"), ("new", "added"))])
    entries.extend(("added", entry) for entry in reviewed["additionalSections"])
    original = []
    for direction, entry in entries:
        identity = dict(publication="26568", direction=direction, entry=entry)
        original.append(dict(id="migration-entry:"+source.entry.digest(identity), kind=source.ENTRY_KIND,
                             state="unresolved", direction=direction, entry=copy.deepcopy(entry)))
    for publication, kinds in (("26568", ("new-and-removed-instruction-entry-review", "changed-source-text-and-encoding-review", "expanded-extension-and-constraint-review")),
                               ("26569", ("publisher-source-status-review", "changed-source-text-and-encoding-review"))):
        original.extend(dict(id=f"migration:{publication}:{kind}", kind=kind, state="unresolved") for kind in kinds)
    entry = dict(originalObligations=original, structuralEntryMappingComplete=True,
                 sourceAdoption=False, semanticEquivalenceEstablished=False, constraintsParsed=False,
                 legalDomainComplete=False, fullAmd64Coverage=False)
    paired = dict(originalMigrationObligations=copy.deepcopy(original), originalHistoricalGaps=2657,
        typedSourceClauses=24, boundaries=copy.deepcopy(source.paired.BOUNDARIES), sourceAdoption=False,
        wholeSectionSemanticsReviewed=False, legalDomainComplete=False, productionAdmission=False, fullAmd64Coverage=False)
    return entry, paired


def unit_adoption_evidence(originals):
    """Small internal-boundary data for reducer controls, not PDF qualification."""
    policy=source.adoption.reviewed_policy(source.entry.read(source.adoption.INPUT))
    return dict(schema=source.adoption.SCHEMA,p1Complete=True,sourceAdoption=True,sourceAuthorityEstablished=True,
        originalObligations=copy.deepcopy(originals),
        sourceSelection=dict(policyInputSha256=source.entry.migration.sha(source.adoption.INPUT),documents=copy.deepcopy(policy["selectedDocuments"])),
        volume5Variant=dict(rule=source.adoption.VARIANT_RULE,pages=[dict(pdfPage=i) for i in range(1,369)]),
        counts=dict(p1MigrationClosed=115,p1MigrationRemaining=0,originalConflictAdjudications=7,
                    tableRelations=33,historicalGaps=2657,additionalSectionsRetained=100),
        p1Dispositions=[dict(originalId=r["id"],originalSha256=source.entry.digest(r),stage="P1",state="closed",
                            rule=source.adoption.migration_rule(r["kind"],policy)) for r in originals],
        constraintsParsed=False,legalDomainComplete=False,productionAdmission=False,fullAmd64Coverage=False)


class MigrationDispositionControls(unittest.TestCase):
    def test_requirements_close_only_after_all_premises_and_no_blockers(self):
        self.assertEqual(source.reduce_requirements(["a","b"],["b","a"],[])["state"],"closed")
        self.assertEqual(source.reduce_requirements(["a","b"],["a"],[])["missing"],["b"])
        self.assertEqual(source.reduce_requirements(["a"],["a"],["source-conflict"])["state"],"open")

    def test_empty_duplicate_and_foreign_requirements_cannot_grant_acceptance(self):
        for args in [([],[],[]),(["a","a"],["a"],[]),(["a"],["b"],[]),(["a"],["a","a"],[]),(["a"],[],["b","b"])]:
            with self.subTest(args=args),self.assertRaises(ValueError):source.reduce_requirements(*args)

    def test_all_original_ids_survive_and_structural_progress_is_separate(self):
        entry, paired = inputs()
        before = copy.deepcopy((entry,paired))
        result = source.derive(entry,paired)
        self.assertEqual((entry,paired),before)
        self.assertEqual(result["originalObligations"],entry["originalObligations"])
        self.assertEqual(result["counts"]["structurallyAccountedEntryRecords"],110)
        self.assertEqual(result["counts"]["structuralFacetsClosed"],111)
        self.assertEqual(result["counts"]["acceptanceRemaining"],115)
        self.assertEqual(result["counts"]["recordsWithSelectedClauses"],8)
        self.assertFalse(result["sourceAdoption"])
        self.assertEqual(len({r["originalId"] for r in result["dispositions"]}),115)

    def test_100_additional_sections_cannot_be_dropped_from_acceptance(self):
        result = source.derive(*inputs())
        additional = [r for r in result["dispositions"] if r["scope"]=="additional-section"]
        self.assertEqual(len(additional),100)
        for row in additional:
            self.assertEqual(row["structural"]["state"],"closed")
            self.assertEqual(row["acceptance"]["state"],"open")
            self.assertIn("p1-source-selection-replay",row["acceptance"]["missing"])
            self.assertNotIn("whole-required-source-review",row["acceptance"]["required"])

    def test_original_omission_duplication_acceptance_and_stable_id_forgery_fail(self):
        for attack in ("omission","duplicate","status","identity","aggregate"):
            entry, paired = inputs()
            if attack=="omission":entry["originalObligations"].pop()
            elif attack=="duplicate":entry["originalObligations"][1]=copy.deepcopy(entry["originalObligations"][0])
            elif attack=="status":entry["originalObligations"][0]["state"]="accepted"
            elif attack=="identity":entry["originalObligations"][0]["id"]="unrelated"
            else:entry["originalObligations"][-1]["id"]="migration:26569:expanded-extension-and-constraint-review"
            paired["originalMigrationObligations"]=copy.deepcopy(entry["originalObligations"])
            with self.subTest(attack=attack),self.assertRaises(ValueError):source.derive(entry,paired)

    def test_clause_counts_flags_and_conflicts_do_not_supply_whole_source_acceptance(self):
        for attack in ("clauses","admission","adoption","semantics","boundary","gap","original"):
            entry, paired = inputs()
            if attack=="clauses":paired["typedSourceClauses"]=100000
            elif attack=="admission":paired["productionAdmission"]=True
            elif attack=="adoption":entry["sourceAdoption"]=True
            elif attack=="semantics":paired["wholeSectionSemanticsReviewed"]=True
            elif attack=="boundary":paired["boundaries"].pop("fma-w")
            elif attack=="gap":paired["originalHistoricalGaps"]-=1
            else:paired["originalMigrationObligations"][0]["id"]="different"
            with self.subTest(attack=attack),self.assertRaises(ValueError):source.derive(entry,paired)

    def test_publisher_marking_conflict_is_a_blocker_with_a_specific_exit_premise(self):
        result = source.derive(*inputs())
        row = next(r for r in result["dispositions"] if r["kind"]=="publisher-source-status-review")
        self.assertIn("publisher-variant-decision-reviewed",row["acceptance"]["missing"])
        self.assertEqual(row["acceptance"]["blockers"],["publisher:26569:variant-selection-replay-required"])

    def test_executed_P1_evidence_can_close_P1_without_closing_P2_or_P3(self):
        entry,paired=inputs();evidence=unit_adoption_evidence(entry["originalObligations"])
        result=source.derive(entry,paired,evidence)
        self.assertTrue(result["sourceAdoption"])
        self.assertEqual(result["counts"]["acceptanceClosed"],115)
        self.assertEqual(result["counts"]["acceptanceRemaining"],0)
        self.assertEqual(result["originalObligations"],entry["originalObligations"])
        self.assertTrue(all(r["state"]=="unresolved" for r in result["originalObligations"]))
        self.assertEqual(result["acceptanceScope"],"P1-source-selection-and-representation-review")
        self.assertTrue(any(r["followUpBlockers"] for r in result["dispositions"]))
        self.assertEqual(sum(bool(r["followUpStages"]) for r in result["dispositions"]),114)

    def test_forged_pass_flag_changed_policy_owner_and_omitted_P1_exit_are_rejected(self):
        entry,paired=inputs()
        for attack in ("flag-only","policy","source","record","hash","kind","variant","count","P2"):
            evidence=unit_adoption_evidence(entry["originalObligations"])
            if attack=="flag-only":evidence={"p1Complete":True}
            elif attack=="policy":evidence["sourceSelection"]["policyInputSha256"]="0"*64
            elif attack=="source":evidence["sourceSelection"]["documents"][0]["pdfSha256"]="0"*64
            elif attack=="record":evidence["p1Dispositions"].pop()
            elif attack=="hash":evidence["p1Dispositions"][0]["originalSha256"]="0"*64
            elif attack=="kind":evidence["p1Dispositions"][0]["stage"]="P2"
            elif attack=="variant":evidence["volume5Variant"]["pages"].pop()
            elif attack=="count":evidence["counts"]["tableRelations"]-=1
            else:evidence["constraintsParsed"]=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):source.derive(entry,paired,evidence)

    def test_conversion_predecessors_are_not_given_replacement_only_source_clauses(self):
        result = source.derive(*inputs())
        originals = {r["id"]:r for r in result["originalObligations"]}
        for row in result["dispositions"]:
            old=originals[row["originalId"]]
            if old["kind"]==source.ENTRY_KIND and old["direction"]=="removed" and old["entry"]["title"] in ("VCVTPH2PS","VCVTPS2PH"):
                self.assertFalse(row["selectedSourceClauses"])

    def test_output_cannot_be_maintained_or_saved_flags_without_source_replay(self):
        with self.assertRaisesRegex(ValueError,"test output must"):
            source.reconstruct(Path("old"),Path("publisher"),source.ROOT/"tests/generated")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"missing"):source.check(Path("old"),Path("publisher"),Path(tmp)/"missing")
            with patch.object(source.paired,"reconstruct",side_effect=ValueError("runtime missing")):
                with self.assertRaisesRegex(ValueError,"runtime missing"):
                    source.reconstruct(Path("old"),Path("publisher"),Path(tmp)/"fresh")
            self.assertFalse((Path(tmp)/"fresh/migration-dispositions.json").exists())


if __name__=="__main__":unittest.main()
