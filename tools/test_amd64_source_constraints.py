"""Source-role omission, substitution and actual geometry controls."""
import copy
import hashlib
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


class ArchitecturalConstraintControls(unittest.TestCase):
    def setUp(self):
        self.pack = domain.read(constraints.ARCHITECTURE_PACK)
        self.actual = domain.read(FIXTURES.parent / 'architecture-source-cells-v1.json')

    def result(self):
        return constraints.validate_architecture_pack_cells(self.pack, self.actual)

    def alter_source_and_reseal(self, publication, identity, update):
        cell = next(c for page in self.actual[publication] for c in page['cells'] if c['id'] == identity)
        update(cell)
        cell['unicodeSha256'] = hashlib.sha256(cell['text'].encode()).hexdigest()
        reference = next(c for c in self.pack['sourceCells'] if c['publication'] == publication and c['id'] == identity)
        reference.update({key: cell[key] for key in reference if key not in {'publication', 'pdfSha256'}})

    def test_selected_architectural_rules_and_unparsed_obligations_are_distinct(self):
        before = copy.deepcopy((self.pack, self.actual))
        result = self.result()
        self.assertEqual(result['sourceCellsReplayed'], 1118)
        self.assertEqual(result['typedClauses'], 24)
        self.assertEqual(len(result['references']), 26)
        self.assertEqual(len(result['unresolvedReferences']), 10)
        self.assertGreater(len(result['unparsedSourceCells']), 500)
        self.assertIn('prefix-note-6', result['unresolvedReferences'])
        self.assertIn('null-segment-prefix-exception', result['unresolvedReferences'])
        for field in ('sourceComplete', 'allArchitecturalConstraintsParsed', 'sourceCellsParsedCompletely', 'fullAmd64Coverage', 'corpusAdoption'):
            self.assertIs(result[field], False)
        self.assertEqual(before, (self.pack, self.actual))

    def test_scope_clause_owner_region_note_and_source_omissions_fail(self):
        for attack in ('clause', 'source-cell', 'footnote', 'owner', 'region', 'publication'):
            self.setUp()
            if attack == 'clause':
                self.pack['clauses'].pop()
            elif attack == 'source-cell':
                self.pack['sourceCells'].pop()
            elif attack == 'footnote':
                self.pack['references'].pop(0)
            elif attack == 'owner':
                self.pack['owners'].pop('sib')
            elif attack == 'region':
                self.pack['regions']['24594'].pop()
            else:
                del self.pack['sources']['24592']
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                constraints.validate_architecture_pack_structure(self.pack)

    def test_wrong_owner_parameter_note_target_and_dependency_are_rejected(self):
        for attack in ('owner', 'parameter', 'footnote-target', 'dependency'):
            self.setUp()
            if attack == 'owner':
                next(c for c in self.pack['clauses'] if c['id'] == 'sib-index4-no-index')['owner'] = 'modrm'
            elif attack == 'parameter':
                next(c for c in self.pack['clauses'] if c['id'] == 'sib-index4-no-index')['parameters']['absentWhenRexX'] = 1
            elif attack == 'footnote-target':
                notes = {c['id']: c for c in self.pack['references']}
                notes['sib-base-note-2']['targetCells'] = notes['sib-index-note-1']['targetCells']
            else:
                next(c for c in self.pack['clauses'] if c['id'] == 'sib-base5-no-base')['dependencies'] = []
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                constraints.validate_architecture_pack_structure(self.pack)

    def test_unresolved_notes_cannot_be_reclassified_as_harmless_or_resolved(self):
        for replacement in ('resolved-location', 'non-encoding-material', 'not-applicable'):
            self.setUp()
            note = next(c for c in self.pack['references'] if c['id'] == 'prefix-note-6')
            note['status'] = replacement
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, 'reference'):
                constraints.validate_architecture_pack_structure(self.pack)

    def test_missing_actual_note_or_cross_volume_source_is_rejected(self):
        for attack in ('note', 'reference-volume', 'duplicate-page', 'wrong-page'):
            self.setUp()
            if attack == 'note':
                page = next(p for p in self.actual['24594'] if p['pdfPage'] == 62)
                page['cells'] = [c for c in page['cells'] if c['id'] != 'pdf:62:cell:36']
            elif attack == 'reference-volume':
                del self.actual['24592']
            elif attack == 'duplicate-page':
                self.actual['24594'].append(copy.deepcopy(self.actual['24594'][0]))
            else:
                self.actual['24592'][0]['cells'][0]['pdfPage'] += 1
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                self.result()

    def test_resealed_source_heading_and_arithmetic_contradictions_fail(self):
        for publication, identity, replacement in (
            ('24594', 'pdf:61:cell:4', 'ModRM Byte Format'),
            ('24592', 'pdf:54:cell:37', 'Address calculations are never truncated to the effective-address size.'),
            ('24594', 'pdf:67:cell:56', 'The address-size prefix disables RIP-relative addressing.'),
        ):
            self.setUp()
            self.alter_source_and_reseal(publication, identity, lambda cell: cell.update(text=replacement))
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, 'heading|reviewed rule'):
                self.result()

    def test_resealed_note_position_and_star_ownership_fail(self):
        for attack in ('note-above-table', 'star-marker'):
            self.setUp()
            if attack == 'note-above-table':
                self.alter_source_and_reseal('24594', 'pdf:62:cell:36', lambda cell: cell.update(rect=[130, 90, 500, 99]))
            else:
                self.alter_source_and_reseal('24594', 'pdf:85:cell:110', lambda cell: cell.update(text='** Not addressable in REX prefix instruction forms'))
            with self.subTest(attack=attack), self.assertRaisesRegex(ValueError, 'footnote'):
                self.result()

    def test_all_global_completeness_promotions_are_rejected(self):
        for field in ('sourceComplete', 'allArchitecturalConstraintsParsed'):
            self.setUp()
            self.pack['scope'][field] = True
            with self.assertRaisesRegex(ValueError, 'completeness'):
                constraints.validate_architecture_pack_structure(self.pack)

    def test_missing_real_pdf_reference_is_not_a_partial_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vol3.pdf'
            path.write_bytes(b'not a pinned source')
            with self.assertRaisesRegex(ValueError, 'actual PDF'):
                constraints.validate_architecture_pack(self.pack, path, path)


if __name__ == "__main__":
    unittest.main()
