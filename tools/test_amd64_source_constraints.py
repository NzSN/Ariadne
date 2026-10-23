"""Source-role omission, substitution and actual geometry controls."""
import copy
import tempfile
from pathlib import Path
import unittest

import amd64_domains as domain
import amd64_source_constraints as constraints

FIXTURES = domain.ROOT / "tests/bap/fixtures/amd64-semantics/mov8-domain"


class SourceConstraintControls(unittest.TestCase):
    def setUp(self):
        self.pack = domain.read(FIXTURES / "source-constraints.json")
        self.actual = domain.read(FIXTURES / "source-cells.json")["pages"]

    def test_exact_292_actual_cells_and_nine_typed_rules(self):
        original = copy.deepcopy(self.pack)
        self.assertEqual(constraints.validate_pack_cells(self.pack, self.actual), 292)
        self.assertEqual(len(self.pack["clauses"]), 9)
        self.assertEqual(self.pack, original)
        self.assertFalse(self.pack["scope"]["sourceComplete"])
        self.assertFalse(self.pack["scope"]["allArchitecturalConstraintsParsed"])

    def test_missing_clause_and_cells_cannot_be_a_smaller_complete_pack(self):
        for attack in ("clause", "cell", "role", "duplicate"):
            item = copy.deepcopy(self.pack)
            if attack == "clause":
                item["clauses"].pop()
            elif attack == "cell":
                item["sourceCells"].pop()
            elif attack == "role":
                item["clauses"][0]["sourceCells"].pop()
            else:
                item["sourceCells"].append(copy.deepcopy(item["sourceCells"][0]))
            with self.assertRaises(ValueError, msg=attack):
                constraints.validate_pack_structure(item)

    def test_rehashed_wrong_direction_alias_or_source_role_is_rejected(self):
        for attack in ("direction", "alias", "role", "unknown"):
            item = copy.deepcopy(self.pack)
            clauses = {row["id"]: row for row in item["clauses"]}
            if attack == "direction":
                clauses["mov8-direction-88"]["parameters"]["source"] = "modrm.rm"
            elif attack == "alias":
                clauses["register-code-map"]["parameters"]["rex"][4] = "ah"
            elif attack == "role":
                clauses["mov8-direction-88"]["sourceCells"] = clauses["mov8-direction-8a"]["sourceCells"]
            else:
                clauses["flags-unmodified"]["kind"] = "unparsed-future-clause"
            with self.assertRaises(ValueError, msg=attack):
                constraints.validate_pack_structure(item)

    def test_source_publication_extractor_and_global_claim_changes_fail(self):
        for attack in ("pdf", "revision", "extractor", "global", "type"):
            item = copy.deepcopy(self.pack)
            if attack == "pdf":
                item["source"]["pdfSha256"] = "0" * 64
            elif attack == "revision":
                item["source"]["revision"] = "3.39"
            elif attack == "extractor":
                item["extractor"]["sourceSha256"][next(iter(item["extractor"]["sourceSha256"]))] = "0" * 64
            elif attack == "global":
                item["scope"]["allArchitecturalConstraintsParsed"] = True
            else:
                item["scope"]["mode"] = 64.0
            with self.assertRaises(ValueError, msg=attack):
                constraints.validate_pack_structure(item)

    def test_actual_geometry_or_unicode_drift_is_not_fixed_by_rehashing_pack(self):
        for field in ("rect", "unicodeSha256", "wordBoxesSha256", "wordSpan"):
            pages = copy.deepcopy(self.actual)
            cell = pages[0]["cells"][0]
            if field in {"rect", "wordSpan"}:
                cell[field][0] += 1
            else:
                cell[field] = "0" * 64
            with self.assertRaises(ValueError, msg=field):
                constraints.validate_pack_cells(self.pack, pages)

    def test_replaced_pdf_bytes_fail_before_geometry_or_positive_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fake.pdf"
            path.write_bytes(b"not the pinned AMD PDF")
            with self.assertRaisesRegex(ValueError, "actual AMD PDF"):
                constraints.validate_pack(self.pack, path, path)

    def test_actual_source_text_and_words_cannot_retain_stale_hashes(self):
        for attack in ("text", "words", "duplicate-cell", "duplicate-page"):
            pages = copy.deepcopy(self.actual)
            if attack == "text":
                pages[0]["cells"][0]["text"] += " changed"
            elif attack == "words":
                pages[0]["cells"][0]["wordBoxes"][0]["text"] += "changed"
            elif attack == "duplicate-cell":
                pages[0]["cells"].append(copy.deepcopy(pages[0]["cells"][0]))
            else:
                pages.append(copy.deepcopy(pages[0]))
            with self.assertRaises(ValueError, msg=attack):
                constraints.validate_pack_cells(self.pack, pages)

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "claim.json"
            for text in ('{"schema":1,"schema":2}', '{"x":NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    domain.read(path)


if __name__ == "__main__":
    unittest.main()
