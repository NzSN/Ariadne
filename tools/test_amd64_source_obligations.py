"""Source-obligation accounting, ownership, omission and forged-decision controls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import amd64_source_obligations as obligations

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/bap/fixtures/source-obligations/source-bundle-excerpt.json'


def inputs():
    bundle = json.loads(FIXTURE.read_text())
    extra = json.loads((FIXTURE.parent / 'distinct-evex-table-cells.json').read_text())
    document = bundle['geometries'][extra['publication']]
    if document['pdfSha256'] != extra['pdfSha256']:
        raise ValueError('distinct table fixture belongs to a different PDF')
    document['content']['sourceCells'].extend(extra['sourceCells'])
    for document in bundle['corpusLock']['documents']:
        if document['publication'] in bundle['geometries']:
            bundle['geometries'][document['publication']]['revision'] = document['revision']
    return bundle, json.loads(obligations.REVIEW.read_text())


def authority_inputs():
    manifest = json.loads(obligations.authority.INPUT.read_text())
    checked = {}
    for issue in manifest['issues']:
        for references in issue['anchors'].values():
            for reference in references:
                checked.setdefault(reference['source'], {})[reference['cell']['id']] = copy.deepcopy(reference['cell'])
    return dict(manifest=manifest, root=ROOT / 'target'), checked


def migration_boundary_result(bundle):
    """Small mocked boundary output for graph controls, never PDF qualification."""
    publishers = {row['publication']: row for row in json.loads(obligations.authority.INPUT.read_text())['sources']}
    documents = []
    for original in bundle['corpusLock']['documents']:
        publication = original['publication']
        if publication not in {'26568', '26569'}:
            continue
        publisher = publishers[publication]
        documents.append(dict(publication=publication,
            oldSource=dict(revision=original['revision'], pdfSha256=original['pdfSha256'], pages=original['pdfPages']),
            newSource=dict(revision=publisher['revision'], pdfSha256=publisher['pdf']['sha256']),
            obligations=[dict(id='mock-review:' + publication, kind='source-review', state='unresolved')],
            sourceAdoption=False, constraintsParsed=False, legalDomainComplete=False))
    return dict(schema=obligations.migration.SCHEMA,
        predecessorLockSha256=bundle['provenance']['corpusLockSha256'],
        historicalGapRecords=sum(len(d['content']['oldGapDispositions']) for d in bundle['geometries'].values()),
        comparisonComplete=True, sourceAdoption=False, constraintsParsed=False, legalDomainComplete=False,
        candidate=dict(path='candidate.json', sha256='0' * 64), documents=documents)


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
        self.assertEqual(result['counts']['tableResolutions'], {'continuation': 26, 'independent-table': 7})
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
                                  ('amd-table:0007', 'amd-table:0008'), ('amd-table:0010', 'amd-table:0011'),
                                  ('amd-table:0262', 'amd-table:0263')})

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
        self.assertEqual(len(series), 26)
        for proof in series:
            self.assertTrue(proof['boundaryCellRoles'])
            self.assertTrue(proof['ownerHeadingCells'])
            for field in ('inheritsOpcodes', 'inheritsOperands', 'inheritsMergedCells', 'inheritsFootnotes'):
                self.assertIs(proof[field], False)
            self.assertIs(proof['leftRow']['inheritsCells'], False)
            self.assertIs(proof['rightRow']['inheritsCells'], False)

    def test_complete_distinct_mnemonic_tables_cannot_be_relabelled_continuation(self):
        bundle, review = inputs()
        decision = next(row for row in review['tableDecisions']
                        if row['rule'] == 'complete-distinct-evex-element-size-tables/v1')
        candidate = obligations._actual_candidates(bundle)[decision['id']]
        decision.update(decision='continuation', rule='same-section-complete-row-series/v1',
                        structure=obligations.structural_evidence(bundle, candidate))
        with self.assertRaisesRegex(ValueError, 'changes explicit mnemonic group'):
            obligations.build_ledger(bundle, review)

    def test_distinct_table_partition_rejects_missing_rows_fields_and_resealed_operands(self):
        for attack in ('missing-row', 'duplicate-row', 'wrong-field', 'wrong-operands', 'moved-encoding'):
            bundle, review = inputs()
            decision = next(row for row in review['tableDecisions']
                            if row['rule'] == 'complete-distinct-evex-element-size-tables/v1')
            candidate = obligations._actual_candidates(bundle)[decision['id']]
            table = candidate['second']
            cells = {cell['id']: cell for cell in bundle['geometries']['26568']['content']['sourceCells']}
            if attack == 'missing-row':
                table['rows'].pop()
            elif attack == 'duplicate-row':
                table['rows'][-1] = table['rows'][0]
            else:
                row = decision['structure']['groups'][1]['rows'][2]
                if attack == 'wrong-field':
                    cell = next(cells[key] for key in row['encodingCells'] if cells[key]['text'] == '1.1111.11')
                    cell['text'] = '0.1111.11'
                elif attack == 'wrong-operands':
                    cells[row['operandCells'][0]]['text'] = 'zmm2/mem256'
                else:
                    cells[row['encodingCells'][0]]['rect'][1] += 12
            with self.subTest(attack=attack), self.assertRaisesRegex(ValueError, 'distinct EVEX table'):
                # Rebuilding the proof itself must fail before a reseal can
                # turn an omitted width/direction or changed source field into acceptance.
                obligations.distinct_evex_table_evidence(bundle, candidate)

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

    def test_fresh_bounded_adjudications_preserve_history_and_unresolved_corpus_adoption(self):
        bundle, review = inputs()
        source_inputs, checked = authority_inputs()
        before = copy.deepcopy(bundle)
        # Only external extraction is replaced by actual small reviewed cells;
        # the authority manifest and semantic proof checker still execute.
        with mock.patch.object(obligations.authority, '_reproduce', return_value=checked) as replay:
            result = obligations.build_ledger(bundle, review, source_inputs)
        replay.assert_called_once()
        self.assertEqual(bundle, before)
        self.assertEqual(result['counts']['sourceConflictsAdjudicated'], 7)
        self.assertTrue(result['acceptance']['sourceConflictsAdjudicated'])
        self.assertFalse(result['acceptance']['sourceAuthorityEstablished'])
        self.assertFalse(result['acceptance']['p1Complete'])
        self.assertFalse(result['acceptance']['selectedConstraintsParsed'])
        for node in result['content']['nodes']:
            if node['kind'] in {'source-conflict', 'source-issue'}:
                self.assertEqual(node['state'], 'adjudicated')
            elif node['kind'] in {'source-authority', 'source-constraint-region', 'coverage-scope'}:
                self.assertEqual(node['resolution'], 'unresolved')
        for publication, document in bundle['geometries'].items():
            self.assertEqual(result['content']['historicalGapRecords'][publication], document['content']['oldGapDispositions'])
        self.assertEqual(result['provenance']['sourceAdjudicationInputs']['reviewedManifestSha256'],
                         obligations.digest(source_inputs['manifest']))

    def test_serialized_authority_results_cannot_replace_fresh_replay(self):
        bundle, review = inputs()
        source_inputs, checked = authority_inputs()
        with mock.patch.object(obligations.authority, '_reproduce', return_value=checked):
            result = obligations.build_ledger(bundle, review, source_inputs)
        with self.assertRaisesRegex(ValueError, 'source inputs fields'):
            obligations.build_ledger(bundle, review, result['provenance']['sourceAdjudicationInputs'])
        with mock.patch.object(obligations.authority, '_reproduce', side_effect=ValueError('fresh PDF mismatch')):
            with self.assertRaisesRegex(ValueError, 'fresh PDF mismatch'):
                obligations.build_ledger(bundle, review, source_inputs)

    def test_authority_result_omission_new_identity_or_scope_promotion_is_rejected(self):
        bundle, review = inputs()
        source_inputs, checked = authority_inputs()
        actual = obligations.authority._adjudicate(source_inputs['manifest'], bundle['geometries'], checked)
        for attack in ('omission', 'new-identity', 'adoption', 'constraint-promotion'):
            changed = copy.deepcopy(actual)
            key = next(iter(changed))
            if attack == 'omission':
                changed.pop(key)
            elif attack == 'new-identity':
                changed['invented-conflict'] = changed.pop(key)
            elif attack == 'adoption':
                changed[key]['corpusAdoption'] = True
            else:
                changed[key]['constraintsParsed'] = True
            with self.subTest(attack=attack), mock.patch.object(obligations.authority, 'validate_adjudications', return_value=changed):
                with self.assertRaisesRegex(ValueError, 'source-conflict identities|source-correction scope'):
                    obligations.build_ledger(bundle, review, source_inputs)

    def test_architectural_clauses_and_open_references_preserve_full_region_obligations(self):
        bundle, review = inputs()
        constraints = obligations.constraints
        pack = constraints.read(constraints.ARCHITECTURE_PACK)
        actual = constraints.read(constraints.ARCHITECTURE_PACK.with_name('architecture-source-cells-v1.json'))
        derived = constraints.validate_architecture_pack_cells(pack, actual)
        source_inputs = dict(pack=pack, pdf=ROOT / 'target/test-vol3.pdf', bbox=ROOT / 'target/test-vol3-bbox.html')
        with mock.patch.object(constraints, 'validate_architecture_pack', return_value=derived) as replay:
            result = obligations.build_ledger(bundle, review, architecture_source_inputs=source_inputs)
        replay.assert_called_once_with(pack, source_inputs['pdf'], source_inputs['bbox'])
        self.assertEqual(result['counts']['typedConstraintClauses'], 24)
        self.assertEqual(result['counts']['constraintReferences'], 26)
        self.assertEqual(result['counts']['unresolvedConstraintReferences'], 10)
        self.assertEqual(result['counts']['unparsedSelectedSourceCells'], len(derived['unparsedSourceCells']))
        regions = [n for n in result['content']['nodes'] if n['kind'] == 'source-constraint-region']
        self.assertEqual(len(regions), 11)
        self.assertTrue(all(n['resolution'] == 'unresolved' and not n['constraintsParsed'] for n in regions))
        self.assertFalse(result['acceptance']['selectedConstraintsParsed'])
        self.assertFalse(result['acceptance']['c2Complete'])
        self.assertFalse(result['acceptance']['sourceAuthorityEstablished'])
        for publication, document in bundle['geometries'].items():
            self.assertEqual(result['content']['historicalGapRecords'][publication], document['content']['oldGapDispositions'])
        self.assertTrue(any(e['relation'] == 'requires-constraint-premise' for e in result['content']['edges']))

    def test_serialized_architectural_assessment_or_promoted_scope_cannot_supply_replay(self):
        bundle, review = inputs()
        constraints = obligations.constraints
        pack = constraints.read(constraints.ARCHITECTURE_PACK)
        actual = constraints.read(constraints.ARCHITECTURE_PACK.with_name('architecture-source-cells-v1.json'))
        derived = constraints.validate_architecture_pack_cells(pack, actual)
        with self.assertRaisesRegex(ValueError, 'architectural source inputs'):
            obligations.build_ledger(bundle, review, architecture_source_inputs=derived)
        derived['allArchitecturalConstraintsParsed'] = True
        with mock.patch.object(constraints, 'validate_architecture_pack', return_value=derived):
            with self.assertRaisesRegex(ValueError, 'selected reviewed scope'):
                obligations.build_ledger(bundle, review, architecture_source_inputs=dict(pack=pack, pdf='unused', bbox='unused'))

    def test_candidate_migration_reviews_are_conditional_and_never_adopt_sources(self):
        bundle, review = inputs()
        result = migration_boundary_result(bundle)
        source_inputs = dict(old_cache=ROOT / 'target/old', publisher_cache=ROOT / 'target/new', output=ROOT / 'target/compared')
        with mock.patch.object(obligations.migration, 'check', return_value=result) as replay:
            ledger = obligations.build_ledger(bundle, review, corpus_migration_inputs=source_inputs)
        replay.assert_called_once_with(**source_inputs)
        branches = [n for n in ledger['content']['nodes'] if n['kind'] == 'source-corpus-candidate']
        self.assertEqual(len(branches), 1)
        self.assertFalse(branches[0]['sourceAdoption'])
        self.assertFalse(branches[0]['mandatoryAdoption'])
        reviews = [n for n in ledger['content']['nodes'] if n['kind'] == 'candidate-source-review']
        self.assertEqual(len(reviews), 2)
        self.assertTrue(all(n['requiredIfCandidateSelected'] and not n['mandatoryAdoption'] for n in reviews))
        authorities = [n for n in ledger['content']['nodes'] if n['kind'] == 'source-authority']
        self.assertEqual(len(authorities), 5)
        self.assertTrue(all(n['resolution'] == 'unresolved' for n in authorities))
        self.assertFalse(ledger['acceptance']['sourceAuthorityEstablished'])
        self.assertEqual(ledger['counts']['candidateMigrationReviewObligations'], 2)
        self.assertTrue(any(e['relation'] == 'requires-review-if-selected' for e in ledger['content']['edges']))

    def test_saved_migration_flags_stale_predecessors_and_adoption_are_rejected(self):
        for attack in ('saved-report', 'stale-predecessor', 'adopted', 'missing-publication', 'resolved-review'):
            bundle, review = inputs()
            result = migration_boundary_result(bundle)
            source_inputs = dict(old_cache='unused', publisher_cache='unused', output='unused')
            if attack == 'saved-report':
                source_inputs = result
            elif attack == 'stale-predecessor':
                result['documents'][0]['oldSource']['pdfSha256'] = '0' * 64
            elif attack == 'adopted':
                result['sourceAdoption'] = True
            elif attack == 'missing-publication':
                result['documents'].pop()
            else:
                result['documents'][0]['obligations'][0]['state'] = 'adjudicated'
            with self.subTest(attack=attack), mock.patch.object(obligations.migration, 'check', return_value=result):
                with self.assertRaisesRegex(ValueError, 'migration'):
                    obligations.build_ledger(bundle, review, corpus_migration_inputs=source_inputs)

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
        self.assertIn('tools/amd64_source_authority.py', original)
        self.assertIn('tests/bap/fixtures/source-authority/adjudications-v1.json', original)
        self.assertIn('tools/amd64_source_constraints.py', original)
        self.assertIn('tests/bap/fixtures/amd64-semantics/architecture-constraints-v1.json', original)
        self.assertIn('tools/amd64_corpus_migration.py', original)
        self.assertIn('tests/bap/fixtures/source-migration/publisher-replacements-v1.json', original)
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            (root / 'tools').mkdir()
            for relative in original:
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_bytes((ROOT / relative).read_bytes())
            self.assertEqual(obligations.source_closure(root), original)
            (root / 'tools/amd64_manual_gap_vol4.py').write_text('# changed recovery implementation\n')
            changed = obligations.source_closure(root)
            self.assertNotEqual(changed, original)
            self.assertEqual({key for key in original if original[key] != changed[key]},
                             {'tools/amd64_manual_gap_vol4.py'})


if __name__ == '__main__':
    unittest.main()
