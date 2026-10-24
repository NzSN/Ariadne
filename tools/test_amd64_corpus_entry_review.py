"""Structural entry mapping controls; synthetic callbacks confer no source pass."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import amd64_corpus_entry_review as review
from amd64_inventory_xed import canonical


def inputs():
    return review.read(review.INPUT)


def comparison(value):
    """Unit-only graph from reviewed addresses, never publisher observations."""
    entries = []
    for link in value["pairedFamilies"]:
        entries.extend([(direction, link[side]) for direction, side in (("removed", "old"), ("added", "new"))])
    entries.extend(("added", entry) for entry in value["additionalSections"])
    obligations = [dict(id=f"unit-entry:{index}", kind="instruction-entry-migration-review", state="unresolved",
                        direction=direction, entry=copy.deepcopy(entry)) for index, (direction, entry) in enumerate(entries)]
    aggregate = lambda prefix, n: [dict(id=f"unit-{prefix}:{i}", kind="unresolved-unit-source-review", state="unresolved") for i in range(n)]
    return dict(sourceAdoption=False, constraintsParsed=False, legalDomainComplete=False, historicalGapRecords=2657,
        documents=[dict(publication="26568", oldSource=dict(pdfSha256=value["oldPdfSha256"]),
            newSource=dict(pdfSha256=value["newPdfSha256"]), obligations=obligations+aggregate("vol4", 3)),
            dict(publication="26569", obligations=aggregate("vol5", 2),
                 sourceStatusConflict=dict(status="unresolved", kind="unit-source-status-marker"))])


def unit_section(side, reference, terms):
    return dict(unitOnly=True, side=side, reference=copy.deepcopy(reference), terms=list(terms))


class CorpusEntryReviewControls(unittest.TestCase):
    def setUp(self):
        self.review = inputs()
        self.source = comparison(self.review)

    def test_reviewed_actual_addresses_cover_five_prior_families_and_100_sections(self):
        review.reviewed_input(self.review)
        self.assertEqual(len(self.review["pairedFamilies"]), 5)
        self.assertEqual(len(self.review["additionalSections"]), 100)
        self.assertEqual(len({row["title"] for row in self.review["additionalSections"]}), 100)

    def test_all_115_original_objects_stay_unresolved_and_immutable(self):
        before = copy.deepcopy((self.source, self.review))
        result = review.classify_changes(self.source, self.review, unit_section)
        self.assertEqual((self.source, self.review), before)
        self.assertEqual(result["counts"], dict(originalObligations=115, entryRecordsMapped=110,
            priorFamilies=5, additionalSections=100, broaderReviewItems=5, originalUnresolvedObligations=115))
        originals = [row for doc in self.source["documents"] for row in doc["obligations"]]
        self.assertEqual(result["originalObligations"], originals)
        mapped = [row[key]["id"] for row in result["priorFamilyLinks"] for key in ("oldObligation", "newObligation")]
        mapped += [row["originalObligation"]["id"] for row in result["additionalSections"]]
        self.assertEqual(len(mapped), len(set(mapped)))
        self.assertEqual(set(mapped), {row["id"] for row in originals if row["kind"] == "instruction-entry-migration-review"})

    def test_missing_duplicate_foreign_or_wrong_extent_pair_is_rejected(self):
        for attack in ("missing", "duplicate", "foreign", "extent", "title"):
            item = copy.deepcopy(self.review)
            if attack == "missing":
                item["pairedFamilies"].pop()
            elif attack == "duplicate":
                item["pairedFamilies"][1] = item["pairedFamilies"][0]
            elif attack == "foreign":
                item["pairedFamilies"][0]["old"]["id"] = "foreign-entry"
            elif attack == "extent":
                item["pairedFamilies"][0]["old"]["pdfEndPage"] += 1
            else:
                item["pairedFamilies"][0]["new"]["title"] = "MOV"
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                review.classify_changes(self.source, item, unit_section)

    def test_new_sections_cannot_be_omitted_duplicated_or_reused_as_a_pair(self):
        for attack in ("omit", "duplicate", "pair", "extra"):
            item = copy.deepcopy(self.review)
            if attack == "omit":
                item["additionalSections"].pop()
            elif attack == "duplicate":
                item["additionalSections"][1] = item["additionalSections"][0]
            elif attack == "pair":
                item["additionalSections"][0] = item["pairedFamilies"][0]["new"]
            else:
                item["additionalSections"].append(item["additionalSections"][0])
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                review.classify_changes(self.source, item, unit_section)

    def test_pdf_or_original_obligation_identity_cannot_be_rewritten(self):
        for attack in ("pdf", "missing", "duplicate", "status", "gap-count", "publication"):
            item = copy.deepcopy(self.source)
            if attack == "pdf":
                item["documents"][0]["oldSource"]["pdfSha256"] = "0"*64
            elif attack == "missing":
                item["documents"][0]["obligations"].pop()
            elif attack == "duplicate":
                item["documents"][0]["obligations"].append(item["documents"][0]["obligations"][0])
            elif attack == "status":
                item["documents"][0]["obligations"][0]["state"] = "resolved"
            elif attack == "gap-count":
                item["historicalGapRecords"] -= 1
            else:
                item["documents"].pop()
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                review.classify_changes(item, self.review, unit_section)

    def test_mapping_never_grants_equivalence_adoption_or_legal_domains(self):
        result = review.classify_changes(self.source, self.review, unit_section)
        self.assertTrue(result["structuralEntryMappingComplete"])
        for field in ("sourceAdoption", "semanticEquivalenceEstablished", "constraintsParsed", "legalDomainComplete", "fullAmd64Coverage"):
            self.assertFalse(result[field])
        self.assertTrue(all(not row["semanticEquivalenceEstablished"] for row in result["priorFamilyLinks"]))
        for field in ("sourceAdoption", "constraintsParsed", "legalDomainComplete"):
            item = copy.deepcopy(self.source); item[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                review.classify_changes(item, self.review, unit_section)

    def test_publisher_marking_conflict_never_disappears_into_revision_equality(self):
        for status in (None, {"status": "resolved"}):
            item = copy.deepcopy(self.source); item["documents"][1]["sourceStatusConflict"] = status
            with self.assertRaisesRegex(ValueError, "source-status conflict"):
                review.classify_changes(item, self.review, unit_section)

    def test_both_source_bodies_are_requested_for_every_prior_family(self):
        calls = []
        def section(side, reference, terms):
            calls.append((side, canonical(reference))); return unit_section(side, reference, terms)
        review.classify_changes(self.source, self.review, section)
        self.assertEqual(sum(side == "predecessor" for side, _ in calls), 5)
        self.assertEqual(sum(side == "replacement" for side, _ in calls), 105)
        self.assertEqual(len(calls), len(set(calls)))

    def test_unreviewed_decision_fields_or_pin_changes_are_rejected(self):
        for field, value in (("decision", "adopted"), ("scopePolicy", "only-old-entries"), ("newPdfSha256", "0"*64)):
            item = copy.deepcopy(self.review); item[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                review.reviewed_input(item)
        with patch.object(review.migration, "sha", return_value="0"*64), self.assertRaisesRegex(ValueError, "input differs"):
            review.reviewed_input(self.review)

    def test_maintained_output_or_saved_report_cannot_supply_a_source_pass(self):
        with self.assertRaisesRegex(ValueError, "test output must"):
            review.reconstruct(Path("old"), Path("new"), review.INPUT.parent/"output")
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "missing"):
            review.check(Path("old"), Path("new"), Path(directory)/"missing")


if __name__ == "__main__":
    unittest.main()
