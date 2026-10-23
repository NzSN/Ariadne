"""Partial-domain relations never promote symbolic-template completeness."""
import copy
import unittest

import amd64_domains as domain
import amd64_reconciliation as reconciliation

FIXTURES = domain.ROOT / "tests/bap/fixtures/amd64-semantics/mov8-domain"


class ReconciliationControls(unittest.TestCase):
    def setUp(self):
        self.domain = domain.read(FIXTURES / "legal-domain.json")
        self.points = domain.validate_mov8_domain(self.domain)
        self.relations = domain.read(FIXTURES / "template-relations.json")
        # These are two actual records for unit controls, intentionally not a
        # complete inventory. Public reconcile() separately verifies the pin.
        self.xed = domain.read(FIXTURES / "xed-records.json")

    def report(self, relations=None, xed=None):
        return reconciliation.reconciliation_report(self.domain, self.points,
            self.relations if relations is None else relations, self.xed if xed is None else xed)

    def test_exact_partial_relations_keep_every_template_remainder_open(self):
        result = self.report()
        self.assertEqual(result["counts"]["finitePoints"], 640)
        self.assertEqual(result["counts"]["partialCandidateRelations"], 2)
        self.assertEqual(result["counts"]["candidateFullDomainBindings"], 0)
        self.assertEqual(result["counts"]["remainingCandidateFullDomains"], 2)
        self.assertTrue(all(row["candidateRemainder"] == "unresolved" for row in result["candidateWorklist"]))
        self.assertTrue(all(not row["producerConsumerBindingEstablished"] for row in result["sourceFormWorklist"]))
        self.assertFalse(result["fullDomainReconciliation"])

    def test_rehashed_full_domain_boolean_and_deleted_remainder_fail(self):
        for attack in ("full", "remainder", "kind"):
            changed = copy.deepcopy(self.relations)
            row = changed["relations"][0]
            if attack == "full":
                row["completeTemplateDomain"] = True
            elif attack == "remainder":
                row["candidateRemainder"] = "empty"
            else:
                row["kind"] = "equivalent-complete-domains"
            with self.assertRaises(ValueError, msg=attack):
                self.report(changed)

    def test_source_domain_cannot_disappear_when_no_template_is_linked(self):
        changed = copy.deepcopy(self.relations)
        removed = changed["relations"].pop()
        with self.assertRaisesRegex(ValueError, "manual legal form omitted"):
            self.report(changed)
        changed["sourceOnlyObligations"].append(dict(form=removed["form"], status="unresolved-template-relation",
            reason="No checked template relation; preserve the AMD source domain as a decoder/producer obligation."))
        result = self.report(changed)
        self.assertEqual(result["counts"]["finiteLegalForms"], 2)
        self.assertEqual(result["counts"]["finitePoints"], 640)
        self.assertEqual(result["counts"]["sourceOnlyObligations"], 1)
        source = next(row for row in result["sourceFormWorklist"] if row["form"] == removed["form"])
        self.assertTrue(source["unmatchedTemplateProducerDecoderObligation"])

    def test_duplicate_or_wrong_candidate_and_direction_are_rejected(self):
        for attack in ("duplicate", "wrong-id", "wrong-pattern", "wrong-operands"):
            changed, xed = copy.deepcopy(self.relations), copy.deepcopy(self.xed)
            if attack == "duplicate":
                changed["relations"].append(copy.deepcopy(changed["relations"][0]))
            elif attack == "wrong-id":
                changed["relations"][0]["candidate"] = changed["relations"][1]["candidate"]
            elif attack == "wrong-pattern":
                xed["records"][0]["source"]["pattern"] += " FUTURE_NONTERMINAL()"
            else:
                xed["records"][0]["source"]["operands"] = "REG0=GPR8_R():w REG1=GPR8_B():r"
            with self.assertRaises(ValueError, msg=attack):
                self.report(changed, xed)

    def test_minimized_records_cannot_pass_as_complete_pinned_inventory(self):
        with self.assertRaises(ValueError):
            reconciliation.reconcile(self.domain, self.relations, self.xed)

    def test_stale_domain_source_and_inventory_identity_fail(self):
        for key in ("domainSha256", "sourcePackSha256", "xedLockSha256", "xedRecordsSha256"):
            changed = copy.deepcopy(self.relations)
            changed[key] = "0" * 64
            with self.assertRaises(ValueError, msg=key):
                self.report(changed)


if __name__ == "__main__":
    unittest.main()
