"""Regression checks for failures that could otherwise hide coverage gaps."""

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import amd64_inventory as inventory


class InventoryTests(unittest.TestCase):
    def test_alias_entries_on_same_page_are_retained(self):
        rows = [
            dict(level=1, title="3 General-Purpose Instruction Reference", pdf_page=10),
            dict(level=2, title="XLAT", pdf_page=12),
            dict(level=2, title="XLATB", pdf_page=12),
            dict(level=2, title="XOR", pdf_page=13),
            dict(level=1, title="4 System Instruction Reference", pdf_page=15),
        ]
        entries = inventory.instruction_entries(rows)
        self.assertEqual([entry["title"] for entry in entries], ["XLAT", "XLATB", "XOR"])
        self.assertEqual([entry["pdf_end_page"] for entry in entries], [12, 12, 14])

    def test_changed_download_is_rejected(self):
        original = b"%PDF-1.7\nfirst"
        source = {"bytes": len(original), "sha256": hashlib.sha256(original).hexdigest()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manual.pdf"
            path.write_bytes(b"%PDF-1.7\nother")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                inventory.verify_pdf(path, source)

    def test_html_download_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manual.pdf"
            path.write_bytes(b"<html>viewer</html>")
            with self.assertRaisesRegex(ValueError, "not a PDF"):
                inventory.verify_pdf(path, {})

    def check_mutated_coverage(self, mutation, message):
        sources = inventory.read_json(inventory.DATA / "manuals.lock.json")["sources"]
        coverage = copy.deepcopy(inventory.read_json(inventory.DATA / "coverage.json"))
        mutation(coverage)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ["instruction-source.json", "source-sections.json"]:
                (root / filename).write_bytes((inventory.DATA / filename).read_bytes())
            (root / "coverage.json").write_text(json.dumps(coverage))
            with patch.object(inventory, "DATA", root), self.assertRaisesRegex(ValueError, message):
                inventory.check(sources, None)

    def test_dropped_instruction_is_rejected(self):
        self.check_mutated_coverage(lambda data: data["instruction_entries"].pop(), "every source entry")

    def test_source_and_coverage_cannot_silently_drop_entry(self):
        sources = inventory.read_json(inventory.DATA / "manuals.lock.json")["sources"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ["instruction-source.json", "source-sections.json", "coverage.json"]:
                data = inventory.read_json(inventory.DATA / filename)
                if filename == "instruction-source.json":
                    data["entries"].pop()
                if filename == "coverage.json":
                    data["instruction_entries"].pop()
                (root / filename).write_text(json.dumps(data))
            with patch.object(inventory, "DATA", root), self.assertRaisesRegex(ValueError, "reviewed lock"):
                inventory.check(sources, None)

    def test_dropped_state_section_is_rejected(self):
        self.check_mutated_coverage(lambda data: data["volume1_sections"].pop(), "every Volume 1 section")

    def test_unsupported_completion_claim_is_rejected(self):
        def mutation(data):
            data["instruction_entries"][0]["status"] = "complete"
        self.check_mutated_coverage(mutation, "Complete instruction needs closed source review|Closing entries requires")

    def test_inventory_does_not_pass_completeness_gate(self):
        sources = inventory.read_json(inventory.DATA / "manuals.lock.json")["sources"]
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "Coverage is pending"):
            inventory.check(sources, None, require_complete=True)

    def assignment_fixture(self):
        assignments = inventory.read_json(inventory.DATA / "work-assignments.json")
        entries = {entry["id"]: entry for entry in
                   inventory.read_json(inventory.DATA / "instruction-source.json")["entries"]}
        return assignments, entries

    def test_all_entries_have_requested_role_and_owner(self):
        assignments, entries = self.assignment_fixture()
        inventory.check_assignments(assignments, entries)

    def test_dropped_assignment_is_rejected(self):
        assignments, entries = self.assignment_fixture()
        assignments["instruction_entries"].pop()
        with self.assertRaisesRegex(ValueError, "every instruction entry"):
            inventory.check_assignments(assignments, entries)

    def test_silent_role_substitution_is_rejected(self):
        assignments, entries = self.assignment_fixture()
        assignments["instruction_entries"][0]["role"] = "worker"
        with self.assertRaisesRegex(ValueError, "user-requested"):
            inventory.check_assignments(assignments, entries)


if __name__ == "__main__":
    unittest.main()
