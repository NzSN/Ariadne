"""Scoped acceptance regressions; tiny proof records below are test fixtures only."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from amd64_profile import REQUIREMENTS, case_digest, digest, inspect, route, targets
from amd64_acceptance import check_ledger
from test_amd64_acceptance import pending_ledger


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.forms = {'authority': {'revision': 'fixture'}, 'forms': [
            {'form_id': 'form', 'entry_ids': ['entry'], 'operands': [
                {'allowed_concrete_kinds': ['gpr', 'memory']}]}]}
        self.profile = {'schema_version': 2, 'id': 'test-user64', 'authority': self.forms['authority'],
            'delivery': 'test fixture', 'execution': {'mode': 'long64', 'cpl': 3},
            'active_milestone': 'register-core',
            'required_case_obligations': sorted(REQUIREMENTS),
            'unsupported_policy': {'foundation_id': 'fallback'},
            'milestones': [{'id': 'register-core', 'operand_projection': 'no-explicit-memory',
                            'form_ids': ['form']}]}
        target = next(iter(targets(self.profile, self.forms).values()))
        self.case_id = target['id']
        self.progress = {'schema_version': 2, 'profile_id': self.profile['id'], 'profile_sha256': digest(self.profile),
            'cases': [dict(target, implementation_stage='paired-body',
                review={'status': 'reviewed', 'source_evidence': ['fixture']},
                semantic_cases=['case'], open_obligations=[])]}
        self.coverage = pending_ledger()
        self.coverage['schema_version'] = 2
        for path, content in [('Rule.tla', 'Rule == TRUE\n'),
                              ('Rule.lean', 'theorem rule : True := True.intro\n')]:
            (self.root/path).write_text(content)
        for kind, path in [('tla-typecheck', 'Rule.tla'), ('tlc', 'Rule.tla'),
                           ('lean-build', 'Rule.lean'), ('lean-axiom-audit', 'Rule.lean')]:
            self.coverage['validation_records'].append(dict(id=kind, kind=kind, result='passed',
                command=['fixture'], summary='Not architectural evidence', sources=[dict(path=path,
                    sha256=hashlib.sha256((self.root/path).read_bytes()).hexdigest())]))
        leaf = dict(status='accepted', description='unit-test mechanism fixture', open_obligations=[],
                    checks=[r['id'] for r in self.coverage['validation_records']],
                    rules=[dict(path='Rule.tla', symbol='Rule'), dict(path='Rule.lean', symbol='rule')])
        self.coverage['foundation_components'] = [dict(copy.deepcopy(leaf), id='fallback',
                                                       profile_sha256=digest(self.profile))]
        self.coverage['semantic_cases'] = [dict(copy.deepcopy(leaf), id='case', form_ids=['form'],
            source_entry_ids=['entry'], profile_scope=dict(profile_id=self.profile['id'],
                profile_sha256=digest(self.profile),
                case_sha256={self.case_id: case_digest(target, self.progress['cases'][0])},
                closed_obligations=sorted(REQUIREMENTS)))]

    def report(self):
        return inspect(self.profile, self.progress, self.coverage, self.forms, None, self.root)

    def refresh_case_hash(self):
        target = targets(self.profile, self.forms)[self.case_id]
        scope = self.coverage['semantic_cases'][0]['profile_scope']
        scope['case_sha256'][self.case_id] = case_digest(target, self.progress['cases'][0])

    def test_scoped_acceptance_does_not_require_full_manual_completion(self):
        result = self.report()
        self.assertTrue(result['milestones'][0]['complete'])
        self.assertEqual(1, result['verified_cases'])
        self.assertEqual([], self.coverage['instruction_entries'])
        self.assertEqual(['gpr', 'memory'], self.forms['forms'][0]['operands'][0]['allowed_concrete_kinds'])
        self.assertEqual([['gpr']], self.progress['cases'][0]['operand_kinds'])

    def test_paired_body_without_step_evidence_is_unsupported(self):
        self.progress['cases'][0]['semantic_cases'] = []
        result = self.report()
        self.assertEqual(1, result['paired_body_cases'])
        self.assertEqual(0, result['verified_cases'])
        self.assertEqual('unsupported', route(self.profile, result, self.case_id, 'long64', 3)['kind'])

    def test_planned_or_partial_body_cannot_be_promoted(self):
        for stage in ['planned', 'partial']:
            with self.subTest(stage=stage):
                self.progress['cases'][0]['implementation_stage'] = stage
                self.refresh_case_hash()
                self.assertEqual(0, self.report()['verified_cases'])

    def test_fallback_must_be_accepted_and_bound_to_this_profile(self):
        self.coverage['foundation_components'][0]['status'] = 'implemented'
        self.assertEqual(0, self.report()['verified_cases'])
        self.coverage['foundation_components'][0]['status'] = 'accepted'
        self.coverage['foundation_components'][0]['profile_sha256'] = 'another-profile'
        self.assertEqual(0, self.report()['verified_cases'])

    def test_relevant_dependencies_are_checked_recursively(self):
        dependency = copy.deepcopy(self.coverage['foundation_components'][0])
        dependency.update(id='profile-dependency', status='implemented')
        self.coverage['system_dependencies'].append(dependency)
        self.coverage['semantic_cases'][0]['dependencies'] = ['profile-dependency']
        with self.assertRaisesRegex(ValueError, 'unaccepted system dependency'):
            self.report()

    def test_missing_obligation_cannot_be_hidden(self):
        self.coverage['semantic_cases'][0]['profile_scope']['closed_obligations'].remove('fault-and-commit-behavior')
        self.assertEqual(0, self.report()['verified_cases'])

    def test_open_obligations_prevent_promotion(self):
        self.progress['cases'][0]['open_obligations'] = ['RIP boundary missing']
        self.refresh_case_hash()
        self.assertEqual(0, self.report()['verified_cases'])

    def test_target_case_cannot_be_dropped(self):
        self.progress['cases'] = []
        with self.assertRaisesRegex(ValueError, 'every targeted case'):
            self.report()

    def test_profile_change_invalidates_progress(self):
        self.profile['execution']['cpl'] = 0
        with self.assertRaisesRegex(ValueError, 'Profile changed'):
            self.report()

    def test_wrong_case_evidence_is_rejected(self):
        self.coverage['semantic_cases'][0]['profile_scope']['case_sha256'][self.case_id] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'another profile/case'):
            self.report()

    def test_complete_source_form_is_part_of_case_identity(self):
        self.forms['forms'][0]['operands'][0]['width_bits'] = 32
        with self.assertRaisesRegex(ValueError, 'Target identity/projection changed'):
            self.report()

    def test_profile_case_review_evidence_is_part_of_case_identity(self):
        self.progress['cases'][0]['review']['source_evidence'] = ['different review']
        with self.assertRaisesRegex(ValueError, 'another profile/case'):
            self.report()

    def test_unrelated_full_manual_evidence_does_not_block_scoped_gate(self):
        unrelated = copy.deepcopy(self.coverage['semantic_cases'][0])
        unrelated['id'] = 'unrelated-roadmap-case'
        unrelated['checks'] = ['stale'] + unrelated['checks'][1:]
        self.coverage['semantic_cases'].append(unrelated)
        self.coverage['validation_records'].append(dict(
            id='stale', kind='tla-typecheck', result='passed', command=['fixture'],
            summary='Unrelated stale roadmap evidence',
            sources=[dict(path='Rule.tla', sha256='0' * 64)]))
        with self.assertRaisesRegex(ValueError, 'Stale validation source'):
            check_ledger(self.coverage, self.root, self.forms, None)
        self.assertEqual(1, self.report()['verified_cases'])

    def test_stale_proof_source_is_rejected(self):
        (self.root/'Rule.lean').write_text('-- changed\n')
        with self.assertRaisesRegex(ValueError, 'Stale validation source'):
            self.report()

    def test_outside_profile_is_unsupported_not_fault_or_noop(self):
        result = self.report()
        self.assertEqual('unsupported', route(self.profile, result, self.case_id, 'protected', 3)['kind'])
        self.assertEqual('unsupported', route(self.profile, result, self.case_id, 'long64', 0)['kind'])
        self.assertEqual('unsupported', route(self.profile, result, 'unlisted', 'long64', 3)['kind'])
        candidate = route(self.profile, result, self.case_id, 'long64', 3)
        self.assertEqual('profile-case-candidate', candidate['kind'])
        self.assertFalse(candidate['certified'])

    def test_forged_report_never_returns_a_runtime_handler(self):
        forged = {'profile_id': self.profile['id'], 'profile_sha256': digest(self.profile),
                  'verified_case_ids': [self.case_id]}
        result = route(self.profile, forged, self.case_id, 'long64', 3)
        self.assertEqual('profile-case-candidate', result['kind'])
        self.assertFalse(result['certified'])

    def test_stale_report_cannot_select_handler(self):
        result = self.report()
        self.profile['delivery'] = 'changed scope'
        self.assertEqual('unsupported', route(self.profile, result, self.case_id, 'long64', 3)['kind'])

    def test_compilation_alone_cannot_close_case(self):
        self.coverage['semantic_cases'][0]['checks'].remove('tlc')
        with self.assertRaisesRegex(ValueError, 'executable TLA'):
            self.report()


if __name__ == '__main__':
    unittest.main()
