#!/usr/bin/env python3
"""Check that mutation qualification requires the named runtime test failure."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import hashlib
import unittest
from unittest.mock import patch

import check_target_resolution_mutations as campaign
from check_target_resolution_mutations import apply_mutation, control_evidence, failure_evidence


class MutationObserverTests(unittest.TestCase):
    def control(self, name='expected_test'):
        return SimpleNamespace(returncode=0, stdout=(
            f'test bap::target_resolution::tests::{name} ... ok\n'
            'test result: ok. 1 passed; 0 failed; 0 ignored\n'))

    def observe(self, output, status=101, expected='expected_test', diagnostic=None):
        return failure_evidence(SimpleNamespace(returncode=status, stdout=output), [expected],
                                self.control(expected), diagnostic)

    def output(self, name, nocapture=False):
        prefix = f'test bap::target_resolution::tests::{name} ... '
        if nocapture:
            prefix += f"\nthread 'bap::target_resolution::tests::{name}' panicked at tests/bap/target_resolution_unit.rs:1:1:\nassertion failed\n"
        return (prefix + 'FAILED\n\nfailures:\n\n'
                f'    bap::target_resolution::tests::{name}\n\n'
                'test result: FAILED. 0 passed; 1 failed; 0 ignored\n')

    def test_named_failure_in_captured_and_serial_nocapture_output(self):
        for nocapture in [False, True]:
            with self.subTest(nocapture=nocapture):
                result = self.observe(self.output('expected_test', nocapture))
                self.assertTrue(result['detected'])
                self.assertEqual(result['failed_tests'], ['bap::target_resolution::tests::expected_test'])

    def test_compile_error_and_unrelated_failure_do_not_qualify(self):
        self.assertFalse(self.observe('error: could not compile ariadne')['detected'])
        self.assertFalse(self.observe(self.output('unrelated_test'))['detected'])
        self.assertFalse(self.observe(self.output('expected_test'), status=1)['detected'])

    def test_test_name_in_panic_text_is_not_a_failed_test(self):
        output = 'thread panicked: expected_test\n' + self.output('unrelated_test')
        self.assertFalse(self.observe(output)['detected'])

    def test_missing_or_failed_unmodified_control_prevents_credit(self):
        failure = SimpleNamespace(returncode=101, stdout=self.output('expected_test'))
        for control in [None, failure, self.control('different_test'),
                        SimpleNamespace(returncode=0, stdout='test result: ok. 0 passed; 0 failed; 1 ignored\n')]:
            self.assertFalse(failure_evidence(failure, ['expected_test'], control)['detected'])

    def test_native_runtime_failure_after_a_passing_control_is_not_arithmetic_detection(self):
        missing = ('called Result::unwrap() on an Err value: Backend("No such file or directory")\n'
                   + self.output('expected_test'))
        self.assertFalse(self.observe(missing, diagnostic='resolver target arithmetic')['detected'])
        semantic = 'native rejected: resolver target arithmetic\n' + self.output('expected_test')
        self.assertTrue(self.observe(semantic, diagnostic='resolver target arithmetic')['detected'])

    def test_control_failure_is_retained_and_aborts_before_mutation(self):
        result = SimpleNamespace(returncode=101, stdout=self.output('expected_test'))
        with TemporaryDirectory() as directory:
            root = Path(directory) / 'repo'
            for folder in ['src', 'tests', 'native/bap', 'native/bap-core',
                           'evidence/Ariadne/indirect-target-resolution/dump048B-20261012']:
                (root / folder).mkdir(parents=True, exist_ok=True)
            for name in ['Cargo.toml', 'Cargo.lock']:
                (root / name).write_text('')
            source = root / 'src/case.rs'
            source.write_text('unmodified')
            output = Path(directory) / 'campaign'
            specs = [('sample', 'src/case.rs', 'unmodified', 'mutated', None)]
            with (patch.object(campaign, 'ROOT', root),
                  patch.object(campaign, 'RUST_MUTATION_TESTS', {'sample': 'expected_test'}),
                  patch.object(campaign, 'mutation_specs', return_value=specs),
                  patch.object(campaign, 'source_inventory', return_value={}),
                  patch.object(campaign.subprocess, 'run', return_value=result),
                  patch('sys.argv', ['campaign', '--output', str(output)])):
                with self.assertRaisesRegex(SystemExit, 'unmodified control did not pass'):
                    campaign.main()
            self.assertEqual(source.read_text(), 'unmodified')
            self.assertEqual((output / 'sample/sut/src/case.rs').read_text(), 'unmodified')
            self.assertTrue((output / 'sample/control.json').is_file())
            self.assertEqual((output / 'sample/control.log').read_text(), result.stdout)

    def test_control_requires_the_selected_runtime_test_to_pass(self):
        self.assertTrue(control_evidence(self.control(), ['expected_test'])['passed'])
        self.assertFalse(control_evidence(self.control(), ['not_exercised'])['passed'])

    def test_retained_checker_rechecks_control_and_native_failure_cause(self):
        import check_target_resolution as checker
        name = 'native-unsigned-offset'
        control = self.control()
        diagnostic = 'resolver target arithmetic'
        result = SimpleNamespace(returncode=101, stdout=diagnostic + '\n' + self.output('expected_test'))
        digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
        baseline = {'native/bap-core/capture.ml': 'a' * 64}
        row = {
            'name': name, **failure_evidence(result, ['expected_test'], control, diagnostic),
            'returncode': 101, 'log_sha256': digest(result.stdout), 'test_binaries': {'sut': 'b' * 64},
            'source_file': 'native/bap-core/capture.ml',
            'control': {**control_evidence(control, ['expected_test']), 'returncode': 0,
                        'log_sha256': digest(control.stdout), 'source_sha256': 'a' * 64,
                        'test_binaries': {'control': 'c' * 64},
                        'helper_manifest': {'handshake': {'source_hashes': {'capture.ml': 'a' * 64}}}},
        }
        report = {'schema': 'ariadne.target-resolution-mutations/v2', 'passed': True,
                  'sources_unchanged': True, 'expected_mutants': [name], 'mutants': [row],
                  'baseline_sources': baseline}
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / name).mkdir()
            (root / name / 'control.log').write_text(control.stdout)
            (root / name / 'test.log').write_text(result.stdout)
            with (patch.object(checker, 'RUST_MUTATION_TESTS', {}),
                  patch.object(checker, 'NATIVE_MUTATION_TESTS', {name: 'expected_test'})):
                checker.verify_mutation_report(report, root / 'report.json')
                missing = 'Backend("No such file or directory")\n' + self.output('expected_test')
                (root / name / 'test.log').write_text(missing)
                row['log_sha256'] = digest(missing)
                with self.assertRaisesRegex(SystemExit, 'semantic diagnostic differs'):
                    checker.verify_mutation_report(report, root / 'report.json')
                (root / name / 'test.log').write_text(result.stdout)
                row['log_sha256'] = digest(result.stdout)
                row['control']['returncode'] = 101
                with self.assertRaisesRegex(SystemExit, 'unmodified control did not pass'):
                    checker.verify_mutation_report(report, root / 'report.json')

    def test_mutation_is_unique_within_its_declared_scope(self):
        self.assertEqual(apply_mutation('first a last a', 'scoped', 'a', 'b', ('first', 'last')),
                         'first b last a')
        with self.assertRaises(SystemExit):
            apply_mutation('a a', 'duplicate', 'a', 'b')


if __name__ == '__main__':
    unittest.main()
