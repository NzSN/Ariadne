"""Source-obligation accounting, ownership, omission and forged-decision controls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import amd64_source_obligations as obligations

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/bap/fixtures/source-obligations/source-bundle-excerpt.json'


def inputs():
    return json.loads(FIXTURE.read_text()), json.loads(obligations.REVIEW.read_text())


class SourceObligationControls(unittest.TestCase):
    def test_exact_seven_records_five_issues_and_all_table_candidates_are_accounted(self):
        bundle, review = inputs()
        before_bundle, before_review = copy.deepcopy(bundle), copy.deepcopy(review)
        result = obligations.build_ledger(bundle, review)
        self.assertEqual(bundle, before_bundle)
        self.assertEqual(review, before_review)
        self.assertEqual(result['counts']['sourceConflictRecords'], 7)
        self.assertEqual(result['counts']['sourceIssues'], 5)
        self.assertEqual(result['counts']['tableCandidates'], 33)
        self.assertEqual(result['counts']['tableResolutions'], {'continuation': 27, 'independent-table': 6})
        self.assertEqual(result['content']['historicalGapRecords']['26568'],
                         bundle['geometries']['26568']['content']['oldGapDispositions'])
        self.assertFalse(result['acceptance']['p1Complete'])
        self.assertFalse(result['acceptance']['selectedConstraintsParsed'])
        self.assertFalse(result['acceptance']['sourceAuthorityEstablished'])
        self.assertTrue(result['acceptance']['initialObligationsAccounted'])

    def test_independent_tables_have_different_purposes_and_exact_encoding_heading(self):
        bundle, review = inputs()
        result = obligations.build_ledger(bundle, review)
        actual = {(node['identity']['fromTable'], node['identity']['toTable']) for node in result['content']['nodes']
                  if node['kind'] == 'table-relation' and node['resolution'] == 'independent-table'}
        self.assertEqual(actual, {('amd-table:0057', 'amd-table:0058'), ('amd-table:0061', 'amd-table:0062'),
                                  ('amd-table:0405', 'amd-table:0406'), ('amd-table:0789', 'amd-table:0790'),
                                  ('amd-table:0007', 'amd-table:0008'), ('amd-table:0010', 'amd-table:0011')})

    def test_omitted_conflict_and_relation_inputs_are_rejected(self):
        for key in ('conflictIssues', 'tableDecisions'):
            bundle, review = inputs()
            review[key].pop()
            with self.assertRaisesRegex(ValueError, 'omit'):
                obligations.build_ledger(bundle, review)

    def test_duplicate_conflict_and_relation_decisions_are_rejected(self):
        for key in ('conflictIssues', 'tableDecisions'):
            bundle, review = inputs()
            review[key].append(copy.deepcopy(review[key][0]))
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                obligations.build_ledger(bundle, review)

    def test_wrong_owner_and_changed_legacy_record_are_rejected(self):
        bundle, review = inputs()
        review['tableDecisions'][0]['historicalEntryIds'] = ['invented-owner']
        with self.assertRaisesRegex(ValueError, 'ownership'):
            obligations.build_ledger(bundle, review)
        bundle, review = inputs()
        bundle['geometries']['26568']['content']['oldGapDispositions'][0]['rationale'] = 'silently repaired'
        with self.assertRaisesRegex(ValueError, 'object or disposition'):
            obligations.build_ledger(bundle, review)

    def test_moved_header_and_missing_boundary_cells_cannot_reuse_a_decision(self):
        for attack in ('moved-header', 'missing-boundary', 'changed-boundary-text'):
            bundle, review = inputs()
            decision = next(row for row in review['tableDecisions'] if row['rule'] == 'semantic-to-explicit-encoding-section/v1')
            cells = bundle['geometries']['26568']['content']['sourceCells']
            if attack == 'moved-header':
                selected = next(cell for cell in cells if cell['id'] == decision['toHeaderCells'][0])
                selected['rect'][1] += 3
                selected['rect'][3] += 3
            else:
                selected = next(cell for cell in cells if cell['id'] == decision['boundaryCells'][0])
                if attack == 'missing-boundary':
                    cells.remove(selected)
                else:
                    selected['text'] = 'Unrelated Section'
            with self.assertRaisesRegex(ValueError, 'source|evidence'):
                obligations.build_ledger(bundle, review)

    def test_resealing_a_wrong_boundary_does_not_make_it_valid(self):
        bundle, review = inputs()
        decision = next(row for row in review['tableDecisions'] if row['rule'] == 'semantic-to-explicit-encoding-section/v1')
        selected = next(cell for cell in bundle['geometries']['26568']['content']['sourceCells']
                        if cell['id'] == decision['boundaryCells'][0])
        selected['text'] = 'Instruction Support'
        decision['sourceCellIdentities'][selected['id']] = obligations.digest(obligations.source_cell_identity(selected))
        with self.assertRaisesRegex(ValueError, 'encoding-section marker'):
            obligations.build_ledger(bundle, review)

    def test_same_heading_does_not_authorize_a_continuation_or_independent_table(self):
        for decision_value in ('continuation', 'independent-table'):
            bundle, review = inputs()
            decision = next(row for row in review['tableDecisions'] if row['identity']['publication'] == '24594')
            decision['decision'] = decision_value
            decision['structure'] = None
            decision['rule'] = 'semantic-to-explicit-encoding-section/v1'
            with self.assertRaisesRegex(ValueError, 'unproved|column purposes'):
                obligations.build_ledger(bundle, review)

    def test_added_intervening_heading_invalidates_independent_table(self):
        bundle, review = inputs()
        decision = next(row for row in review['tableDecisions'] if row['rule'] == 'semantic-to-explicit-encoding-section/v1')
        cells = bundle['geometries']['26568']['content']['sourceCells']
        marker = next(cell for cell in cells if cell['id'] == decision['boundaryCells'][0])
        extra = copy.deepcopy(marker)
        extra['id'] = 'attack-heading'
        extra['text'] = 'Instruction Support'
        extra['rect'][1] += 2
        extra['rect'][3] += 2
        cells.append(extra)
        with self.assertRaisesRegex(ValueError, 'intervening'):
            obligations.build_ledger(bundle, review)

    def test_series_omission_wrong_column_missing_opcode_and_cross_page_fragment_fail(self):
        for attack in ('omitted-footer', 'wrong-column', 'missing-opcode', 'cross-page-fragment'):
            bundle, review = inputs()
            decision = next(row for row in review['tableDecisions']
                            if row['identity']['publication'] == '24594' and row['identity']['fromTable'] == 'amd-table:0004')
            cells = bundle['geometries']['24594']['content']['sourceCells']
            proof = decision['structure']
            if attack == 'omitted-footer':
                identity = next(key for key, role in proof['boundaryCellRoles'].items() if role == 'running-page-footer')
                cells.remove(next(cell for cell in cells if cell['id'] == identity))
            else:
                selected = next(cell for cell in cells if cell['id'] == proof['leftRow']['encodingCells'][0])
                if attack == 'wrong-column':
                    selected['rect'][0] += 200
                    selected['rect'][2] += 200
                elif attack == 'missing-opcode':
                    cells.remove(selected)
                else:
                    selected['pdfPage'] += 1
            with self.assertRaisesRegex(ValueError, 'boundary|cross-page'):
                obligations.build_ledger(bundle, review)

    def test_series_inserted_section_heading_and_inherited_footnote_claim_fail(self):
        for attack in ('heading', 'footnote-inheritance'):
            bundle, review = inputs()
            decision = next(row for row in review['tableDecisions']
                            if row['identity']['publication'] == '24594' and row['identity']['fromTable'] == 'amd-table:0004')
            if attack == 'heading':
                cells = bundle['geometries']['24594']['content']['sourceCells']
                original = next(cell for cell in cells if cell['id'] == decision['structure']['ownerHeadingCells'][0])
                extra = copy.deepcopy(original)
                extra.update(id='attack-intervening-owner', text='SUB', pdfPage=128,
                             rect=[63, 80, 100, 103])
                cells.append(extra)
            else:
                decision['structure']['inheritsFootnotes'] = True
            with self.assertRaisesRegex(ValueError, 'heading|boundary'):
                obligations.build_ledger(bundle, review)

    def test_series_never_inherits_row_cells_or_footnotes(self):
        bundle, review = inputs()
        result = obligations.build_ledger(bundle, review)
        series = [node['structure'] for node in result['content']['nodes']
                  if node['kind'] == 'table-relation' and node['resolution'] == 'continuation']
        self.assertEqual(len(series), 27)
        for proof in series:
            self.assertTrue(proof['boundaryCellRoles'])
            self.assertTrue(proof['ownerHeadingCells'])
            for field in ('inheritsOpcodes', 'inheritsOperands', 'inheritsMergedCells', 'inheritsFootnotes'):
                self.assertIs(proof[field], False)
            self.assertIs(proof['leftRow']['inheritsCells'], False)
            self.assertIs(proof['rightRow']['inheritsCells'], False)

    def test_source_scope_region_or_page_omission_is_rejected(self):
        for attack in ('scope', 'region', 'page', 'volume'):
            bundle, review = inputs()
            if attack == 'scope':
                bundle['corpusLock']['scope']['vendor'] = 'Intel'
            elif attack == 'region':
                bundle['regions']['content']['documents'][0]['requiredRegions'].pop()
            elif attack == 'page':
                bundle['regions']['content']['documents'][0]['pages'].pop()
            else:
                del bundle['geometries']['26569']
            with self.assertRaisesRegex(ValueError, 'scope|region|page|volume'):
                obligations.build_ledger(bundle, review)

    def test_input_passed_flags_cannot_establish_constraints_or_source_authority(self):
        bundle, review = inputs()
        for document in bundle['geometries'].values():
            document['acceptance'] = dict(sourceCompletenessEstablished=True, c2Complete=True)
        result = obligations.build_ledger(bundle, review)
        self.assertFalse(result['acceptance']['c2Complete'])
        self.assertFalse(result['acceptance']['sourceAuthorityEstablished'])
        review['accepted'] = True
        with self.assertRaisesRegex(ValueError, 'fields'):
            obligations.build_ledger(bundle, review)

    def test_output_omission_owner_rewrite_and_forged_acceptance_are_not_resealable(self):
        bundle, review = inputs()
        expected = obligations.build_ledger(bundle, review)
        for attack in ('node', 'edge', 'owner', 'history', 'acceptance'):
            changed = copy.deepcopy(expected)
            if attack == 'node':
                changed['content']['nodes'].pop()
            elif attack == 'edge':
                changed['content']['edges'].pop()
            elif attack == 'owner':
                node = next(row for row in changed['content']['nodes'] if row['kind'] == 'table-relation')
                node['historicalEntryIds'] = ['forged-owner']
            elif attack == 'history':
                changed['content']['historicalGapRecords']['26568'].pop()
            else:
                changed['acceptance']['p1Complete'] = True
            changed['contentSha256'] = obligations.digest(changed['content'])
            with self.assertRaisesRegex(ValueError, 'complete source reconstruction'):
                obligations.check_ledger(changed, expected)

    def test_dependency_closure_includes_recovery_modules_and_obligation_implementation(self):
        original = obligations.source_closure()
        self.assertIn('tools/amd64_source_obligations.py', original)
        self.assertIn('tools/amd64_manual_gap_vol4.py', original)
        self.assertIn('tools/amd64_manual_outline.js', original)
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            (root / 'tools').mkdir()
            for relative in original:
                (root / relative).write_bytes((ROOT / relative).read_bytes())
            self.assertEqual(obligations.source_closure(root), original)
            (root / 'tools/amd64_manual_gap_vol4.py').write_text('# changed recovery implementation\n')
            changed = obligations.source_closure(root)
            self.assertNotEqual(changed, original)
            self.assertEqual({key for key in original if original[key] != changed[key]},
                             {'tools/amd64_manual_gap_vol4.py'})


if __name__ == '__main__':
    unittest.main()
