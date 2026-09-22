"""Evidence freshness and closure regressions for the semantic coverage gate."""

import hashlib
from pathlib import Path
import tempfile
import unittest

from amd64_acceptance import INTEGRATION_OBLIGATIONS, check_ledger


def pending_ledger():
    return dict(
        instruction_entries=[], volume1_sections=[], semantic_cases=[], state_components=[],
        system_dependencies=[], validation_records=[],
        integration_obligations=[dict(id=name, status="pending") for name in sorted(INTEGRATION_OBLIGATIONS)],
    )


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        # These tiny sources are test fixtures for the ledger mechanism, not
        # claimed AMD semantics or actual checker results.
        (self.root / "Rule.tla").write_text("Rule == TRUE\n")
        (self.root / "Rule.lean").write_text("theorem rule : True := True.intro\n")
        self.ledger = pending_ledger()
        for kind, path in [("tla-typecheck", "Rule.tla"), ("tlc", "Rule.tla"),
                           ("lean-build", "Rule.lean"), ("lean-axiom-audit", "Rule.lean")]:
            self.ledger["validation_records"].append(dict(
                id=kind, kind=kind, result="passed", command=["fixture-check"], summary="unit-test fixture",
                sources=[dict(path=path, sha256=hashlib.sha256((self.root / path).read_bytes()).hexdigest())],
            ))
        self.leaf = dict(
            id="fixture-component", status="accepted", description="A component, not an entire instruction",
            open_obligations=[], checks=[r["id"] for r in self.ledger["validation_records"]],
            rules=[dict(path="Rule.tla", symbol="Rule"), dict(path="Rule.lean", symbol="rule")],
            field_ids=["fixture-field"], dependencies=[],
        )

    def test_component_acceptance_does_not_complete_isa(self):
        self.ledger["state_components"] = [self.leaf]
        result = check_ledger(self.ledger, self.root)
        self.assertEqual(result["accepted_state_components"], 1)
        self.assertFalse(result["complete"])

    def test_changed_source_invalidates_check(self):
        (self.root / "Rule.lean").write_text("-- changed after checking\n")
        with self.assertRaisesRegex(ValueError, "Stale validation source"):
            check_ledger(self.ledger, self.root)

    def test_missing_machine_check_cannot_be_replaced_by_claim(self):
        self.leaf["checks"].remove("lean-axiom-audit")
        self.ledger["state_components"] = [self.leaf]
        with self.assertRaisesRegex(ValueError, r"Missing TLA\+/Lean evidence"):
            check_ledger(self.ledger, self.root)

    def test_open_obligation_prevents_acceptance(self):
        self.leaf["open_obligations"] = ["fault behavior not implemented"]
        self.ledger["semantic_cases"] = [self.leaf]
        with self.assertRaisesRegex(ValueError, "unclosed scope"):
            check_ledger(self.ledger, self.root)

    def test_empty_form_list_cannot_close_instruction(self):
        self.ledger["instruction_entries"] = [dict(id="entry", status="complete", review_complete=True,
                                                    open_obligations=[], form_ids=[], semantic_cases=[])]
        with self.assertRaisesRegex(ValueError, "entire form inventory"):
            check_ledger(self.ledger, self.root, forms={"forms": []})

    def test_unreviewed_form_cannot_close_instruction(self):
        self.ledger["instruction_entries"] = [dict(id="entry", status="complete", review_complete=True,
                                                    open_obligations=[], form_ids=["form"], semantic_cases=[])]
        forms = dict(forms=[dict(form_id="form", entry_ids=["entry"],
                                 review=dict(level="table-reconciled", status="pending-semantic-review"))])
        with self.assertRaisesRegex(ValueError, "unreviewed form"):
            check_ledger(self.ledger, self.root, forms=forms)

    def test_removing_integration_obligation_is_rejected(self):
        self.ledger["integration_obligations"].pop()
        with self.assertRaisesRegex(ValueError, "Integration obligations"):
            check_ledger(self.ledger, self.root)

    def test_evidence_for_different_lean_file_is_not_sufficient(self):
        (self.root / "Other.lean").write_text("-- another source\n")
        record = next(r for r in self.ledger["validation_records"] if r["kind"] == "lean-axiom-audit")
        record["sources"] = [dict(path="Other.lean", sha256=hashlib.sha256((self.root / "Other.lean").read_bytes()).hexdigest())]
        self.ledger["state_components"] = [self.leaf]
        with self.assertRaisesRegex(ValueError, "both build and axiom-audit"):
            check_ledger(self.ledger, self.root)

    def test_unaccepted_dependency_prevents_acceptance(self):
        self.ledger["system_dependencies"] = [dict(id="protection", status="pending")]
        self.leaf["dependencies"] = ["protection"]
        self.ledger["state_components"] = [self.leaf]
        with self.assertRaisesRegex(ValueError, "unaccepted dependency"):
            check_ledger(self.ledger, self.root)


if __name__ == "__main__":
    unittest.main()
