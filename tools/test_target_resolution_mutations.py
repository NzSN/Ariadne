#!/usr/bin/env python3
"""Check that mutation qualification requires the named runtime test failure."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import hashlib
import json
import io
import signal
import subprocess
import sys
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

    def make_repo(self, directory):
        root = Path(directory) / 'repo'
        for folder in campaign.INPUT_TREES + campaign.FIXTURE_TREES:
            (root / folder).mkdir(parents=True, exist_ok=True)
            (root / folder / 'input.txt').write_text(folder)
        (root / 'native/bap-core').mkdir(parents=True)
        (root / 'native/bap-core/legacy_capture.ml').write_text('Int64.add base (signed raw 32)')
        (root / 'native/bap-core/capture.ml').write_text('current profile arithmetic')
        (root / 'Cargo.toml').write_text('path = "../MirrorRust"\n')
        (root / 'Cargo.lock').write_text('locked')
        (root / 'src/case.rs').write_text('unmodified')
        return root

    def fixture_campaign(self, root, output, observe, native=False):
        specs = [('sample', 'src/case.rs', 'unmodified', 'mutated', None)]
        return (patch.object(campaign, 'ROOT', root),
                patch.object(campaign, 'RUST_MUTATION_TESTS', {'sample': 'expected_test'}),
                patch.object(campaign, 'mutation_specs', return_value=specs),
                patch.object(campaign, 'run_command', side_effect=observe),
                patch('sys.argv', ['campaign', '--output', str(output)] + (['--native'] if native else [])))

    def run_fixture_campaign(self, root, output, observe, native=False):
        from contextlib import ExitStack, redirect_stdout
        with ExitStack() as stack:
            stack.enter_context(redirect_stdout(io.StringIO()))
            for context in self.fixture_campaign(root, output, observe, native=native):
                stack.enter_context(context)
            campaign.main()

    def runtime_result(self, command, cwd, passed):
        build = Path(command[command.index('--target-dir') + 1])
        executable = build / 'debug/deps/ariadne-observer'
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text('control executable' if passed else 'mutant executable')
        artifact = json.dumps({'reason': 'compiler-artifact', 'executable': str(executable)})
        test = command[command.index('--lib') + 1].rsplit('::', 1)[-1]
        text = self.control(test).stdout if passed else self.output(test)
        return SimpleNamespace(returncode=0 if passed else 101, stdout=artifact + '\n' + text,
                               timed_out=False)

    def test_control_failure_is_retained_and_aborts_before_mutation(self):
        result = SimpleNamespace(returncode=101, stdout=self.output('expected_test'), timed_out=False)
        with TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            source = root / 'src/case.rs'
            output = Path(directory) / 'campaign'
            with self.assertRaisesRegex(SystemExit, 'unmodified control did not pass'):
                self.run_fixture_campaign(root, output, lambda *args: result)
            self.assertEqual(source.read_text(), 'unmodified')
            self.assertEqual((output / 'sample/sut/src/case.rs').read_text(), 'unmodified')
            self.assertTrue((output / 'sample/control.json').is_file())
            self.assertEqual((output / 'sample/control.log').read_text(), result.stdout)
            report = json.loads((output / 'report.json').read_text())
            self.assertFalse(report['passed'])
            self.assertFalse(report['complete'])
            self.assertIn('unmodified control did not pass', report['failure']['message'])

    def test_copy_preserves_all_compile_inputs_before_manifest_rewrite(self):
        with TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            # Real current compile-time model and generated binding inputs.
            (root / 'Specs/model.tla').write_bytes(b'model\r\n')
            (root / 'mbt/binding.rs').write_bytes(b'binding\r\n')
            (root / 'tools/observer.py').write_text('observer')
            checkout = Path(directory) / 'copy'
            checkout.mkdir()
            with patch.object(campaign, 'ROOT', root):
                baseline = campaign.source_inventory()
                manifest = campaign.copy_inputs(checkout, baseline)
                for name, digest in baseline.items():
                    if name != 'Cargo.toml':
                        self.assertEqual(campaign.sha(checkout / name), digest)
                self.assertNotEqual(campaign.sha(manifest), baseline['Cargo.toml'])
                self.assertIn(str(root.parent / 'MirrorRust'), manifest.read_text())
                self.assertEqual((checkout / 'Specs/model.tla').read_bytes(), b'model\r\n')

    def test_copy_rejects_changed_or_missing_inputs_before_dependency_rewrite(self):
        for change in ('changed', 'missing'):
            with self.subTest(change=change), TemporaryDirectory() as directory:
                root = self.make_repo(directory)
                checkout = Path(directory) / 'copy'
                checkout.mkdir()
                with patch.object(campaign, 'ROOT', root):
                    baseline = campaign.source_inventory()
                    path = root / 'Specs/input.txt'
                    path.write_text('changed') if change == 'changed' else path.unlink()
                    with self.assertRaisesRegex(SystemExit, 'copied qualification inputs differ'):
                        campaign.copy_inputs(checkout, baseline)
                    self.assertEqual((checkout / 'Cargo.toml').read_text(), 'path = "../MirrorRust"\n')

    def test_success_publishes_only_after_mutation_and_complete_stable_inventory(self):
        with TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            output = Path(directory) / 'campaign'
            calls = []
            def observe(command, cwd, env):
                report = json.loads((output / 'report.json').read_text())
                self.assertFalse(report['passed'])
                self.assertFalse(report['complete'])
                self.assertIn('--exact', command)
                self.assertEqual(command[command.index('-j') + 1], '1')
                calls.append((Path(cwd) / 'src/case.rs').read_text())
                return self.runtime_result(command, cwd, passed=len(calls) == 1)
            self.run_fixture_campaign(root, output, observe)
            self.assertEqual(calls, ['unmodified', 'mutated'])
            report = json.loads((output / 'report.json').read_text())
            self.assertTrue(report['passed'])
            self.assertTrue(report['complete'])
            self.assertTrue(report['sources_unchanged'])
            self.assertEqual(report['baseline_sources'], report['final_sources'])
            self.assertFalse((output / 'report.json.tmp').exists())

    def test_added_removed_and_changed_source_fail_without_passing_receipt(self):
        for change in ('added', 'removed', 'changed'):
            with self.subTest(change=change), TemporaryDirectory() as directory:
                root = self.make_repo(directory)
                output = Path(directory) / 'campaign'
                calls = []
                def observe(command, cwd, env):
                    calls.append(command)
                    if len(calls) == 2:
                        path = root / ('Specs/new.tla' if change == 'added' else 'Specs/input.txt')
                        path.unlink() if change == 'removed' else path.write_text('drift')
                    return self.runtime_result(command, cwd, passed=len(calls) == 1)
                with self.assertRaisesRegex(SystemExit, 'qualification source changed'):
                    self.run_fixture_campaign(root, output, observe)
                report = json.loads((output / 'report.json').read_text())
                self.assertFalse(report['passed'])
                self.assertFalse(report['complete'])
                self.assertFalse(report['sources_unchanged'])
                self.assertEqual(len(report['source_changes'][change]), 1)

    def test_passing_mutant_or_stale_control_binary_never_qualifies(self):
        for mode in ('survives', 'stale'):
            with self.subTest(mode=mode), TemporaryDirectory() as directory:
                root = self.make_repo(directory)
                output = Path(directory) / 'campaign'
                calls = []
                def observe(command, cwd, env):
                    calls.append(command)
                    result = self.runtime_result(command, cwd, passed=len(calls) == 1 or mode == 'survives')
                    if len(calls) == 2 and mode == 'stale':
                        build = Path(command[command.index('--target-dir') + 1])
                        (build / 'debug/deps/ariadne-observer').write_text('control executable')
                    return result
                with self.assertRaisesRegex(SystemExit, 'mutant escaped'):
                    self.run_fixture_campaign(root, output, observe)
                self.assertFalse(json.loads((output / 'report.json').read_text())['passed'])

    def test_incomplete_or_unstable_report_cannot_be_published_as_success(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            for records, final in (([], {'input': 'a'}),
                                   ([{'name': 'sample', 'detected': True}], {'input': 'b'}),
                                   ([{'name': 'sample', 'detected': False}], {'input': 'a'})):
                with self.subTest(records=records, final=final), self.assertRaisesRegex(SystemExit, 'cannot pass'):
                    campaign.write_report(output, records, {'input': 'a'}, {'sample'}, final, passed=True)
                self.assertFalse((output / 'report.json').exists())

    def test_compiler_identity_does_not_use_unreported_or_external_executables(self):
        with TemporaryDirectory() as directory:
            build = Path(directory) / 'build'
            build.mkdir()
            stale = build / 'stale'
            stale.write_text('stale')
            self.assertEqual(campaign.binary_identities(build, ''), {})
            outside = Path(directory) / 'external'
            outside.write_text('external')
            text = json.dumps({'reason': 'compiler-artifact', 'executable': str(outside)})
            with self.assertRaisesRegex(SystemExit, 'outside its isolated build'):
                campaign.binary_identities(build, text)

    def test_timeout_and_interrupt_cleanup_the_compiler_process_group(self):
        for error in (subprocess.TimeoutExpired('command', 1), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                process = SimpleNamespace(pid=1234, returncode=-9)
                process.communicate = unittest.mock.Mock(side_effect=[error, ('partial output', None)])
                process.wait = unittest.mock.Mock(return_value=-15)
                with (patch.object(campaign.subprocess, 'Popen', return_value=process) as popen,
                      patch.object(campaign.os, 'killpg') as kill):
                    if isinstance(error, KeyboardInterrupt):
                        with self.assertRaises(KeyboardInterrupt):
                            campaign.run_command(['command'], Path('/tmp'))
                    else:
                        result = campaign.run_command(['command'], Path('/tmp'), timeout=1)
                        self.assertIsNone(result.returncode)
                        self.assertTrue(result.timed_out)
                    self.assertTrue(popen.call_args.kwargs['start_new_session'])
                    self.assertEqual(kill.call_args_list,
                                     [unittest.mock.call(1234, signal.SIGTERM),
                                      unittest.mock.call(1234, signal.SIGKILL)])

    def test_child_stderr_cannot_split_control_status_or_hide_arithmetic_rejection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            prefix = 'test bap::target_resolution::tests::expected_test ... '
            summary = 'test result: ok. 1 passed; 0 failed; 0 ignored\n'
            script = ('import sys; '
                      + 'sys.stdout.write(' + repr(prefix) + '); sys.stdout.flush(); '
                      + 'sys.stderr.write("native helper diagnostic\\n"); sys.stderr.flush(); '
                      + 'sys.stdout.write(' + repr('ok\n' + summary) + '); sys.stdout.flush()')
            control = campaign.run_command([sys.executable, '-c', script], root)
            self.assertTrue(control_evidence(control, ['expected_test'])['passed'])
            self.assertEqual(control.captured_stdout, prefix + 'ok\n' + summary)
            self.assertEqual(control.captured_stderr, 'native helper diagnostic\n')
            # The original merged-stream ordering loses the exact success line.
            mixed = SimpleNamespace(returncode=0, stdout=prefix + control.captured_stderr + 'ok\n' + summary)
            self.assertFalse(control_evidence(mixed, ['expected_test'])['passed'])
            failure_stdout = self.output('expected_test', nocapture=True)
            failure_script = ('import sys; sys.stdout.write(' + repr(failure_stdout) + '); '
                              + 'sys.stdout.flush(); sys.stderr.write("fatal: resolver target arithmetic\\n"); '
                              + 'sys.stderr.flush(); sys.exit(101)')
            mutant = campaign.run_command([sys.executable, '-c', failure_script], root)
            observation = failure_evidence(mutant, ['expected_test'], control, 'resolver target arithmetic')
            self.assertTrue(observation['detected'])
            logs = campaign.command_logs(root, 'native', mutant)
            self.assertEqual((root / 'native.stdout.log').read_text(), failure_stdout)
            self.assertEqual((root / 'native.stderr.log').read_text(), mutant.captured_stderr)
            self.assertEqual(logs['output_streams']['stderr']['sha256'],
                             campaign.sha(root / 'native.stderr.log'))
            eof = campaign.command_result(101, failure_stdout, 'fatal: unexpected EOF\n', False)
            self.assertFalse(failure_evidence(eof, ['expected_test'], control,
                                             'resolver target arithmetic')['detected'])

    def test_native_seam_is_checked_even_for_static_preflight(self):
        with TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            (root / 'native/bap-core/legacy_capture.ml').write_text('changed native arithmetic')
            specs = [('sample', 'src/case.rs', 'unmodified', 'mutated', None)]
            with (patch.object(campaign, 'ROOT', root),
                  patch.object(campaign, 'RUST_MUTATION_TESTS', {'sample': 'expected_test'}),
                  patch.object(campaign, 'mutation_specs', return_value=specs),
                  patch('sys.argv', ['campaign', '--check-seams'])):
                with self.assertRaisesRegex(SystemExit, 'native-unsigned-offset'):
                    campaign.main()

    def native_routing_fixture(self, root):
        test = campaign.NATIVE_MUTATION_TESTS['native-unsigned-offset']
        (root / 'tests/input').mkdir(parents=True, exist_ok=True)
        (root / 'tests/input/target_resolution_unit.rs').write_text(
            'fn ' + test + '() { snapshot.prepare_with_bap_target_resolution(); }\n')
        capture = root / 'native/bap-core/capture.ml'
        capture.write_text(
            'let current_arithmetic = Int64.add base (signed raw 32)\n'
            'let admit_resolved ?loop_checker j snapshot =\n'
            '  let report=get j "target_resolution" in\n'
            '  if string report "schema"="ariadne.indirect-target-resolution/v3" then\n'
            '    admit_resolved_current ~loop_checker j snapshot\n'
            '  else Legacy_capture.admit_resolved j snapshot\n')
        legacy = root / 'native/bap-core/legacy_capture.ml'
        legacy.write_text(
            'string report "schema"="ariadne.indirect-target-resolution/v1" &&\n'
            'string report "profile"="captured-indirect-targets/v1"\n'
            'Int64.add base (signed raw 32)\n')
        return capture, legacy

    def test_preflight_rejects_native_observer_profile_or_translation_unit_drift(self):
        for drift in ('preparation', 'dispatch', 'translation-unit'):
            with self.subTest(drift=drift), TemporaryDirectory() as directory:
                root = self.make_repo(directory)
                capture, _ = self.native_routing_fixture(root)
                with patch.object(campaign, 'ROOT', root):
                    binding = campaign.native_observer_binding()
                    self.assertEqual(binding['source_file'], 'native/bap-core/legacy_capture.ml')
                    if drift == 'preparation':
                        test = root / 'tests/input/target_resolution_unit.rs'
                        test.write_text(test.read_text().replace('prepare_with_bap_target_resolution',
                                                                 'prepare_with_bap_target_candidates'))
                        with self.assertRaisesRegex(SystemExit, 'preparation/profile changed'):
                            campaign.native_observer_binding()
                    elif drift == 'dispatch':
                        capture.write_text(capture.read_text().replace('v3', 'v1'))
                        with self.assertRaisesRegex(SystemExit, 'profile dispatch changed'):
                            campaign.native_observer_binding()
                    else:
                        name, _, before, after, scope = campaign.native_mutation_spec()
                        with patch.object(campaign, 'native_mutation_spec', return_value=(
                                name, 'native/bap-core/capture.ml', before, after, scope)):
                            with self.assertRaisesRegex(SystemExit, 'translation unit does not match'):
                                campaign.native_observer_binding()

    def test_native_campaign_mutates_the_declared_active_file_and_keeps_current_code(self):
        with TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            for name in campaign.NATIVE_HELPER_SOURCES:
                (root / 'native/bap-core' / name).write_text(name)
            capture, legacy = self.native_routing_fixture(root)
            capture_bytes, legacy_bytes = capture.read_bytes(), legacy.read_bytes()
            output = root / 'target/campaign'
            observed_builds = []
            calls = []
            diagnostic_envs = []
            def build(case, sources, helper, label, env):
                self.assertEqual((sources / 'capture.ml').read_bytes(), capture_bytes)
                current = (sources / 'legacy_capture.ml').read_bytes()
                if label == 'control-build':
                    self.assertEqual(current, legacy_bytes)
                else:
                    self.assertEqual(current, legacy_bytes.replace(
                        b'Int64.add base (signed raw 32)', b'Int64.add base raw'))
                observed_builds.append(label)
                return {'handshake': {'source_hashes': {
                    name: campaign.sha(sources / name) for name in campaign.NATIVE_HELPER_SOURCES}},
                    'helper_sha256': hashlib.sha256(current + capture_bytes).hexdigest()}
            def observe(command, cwd, env):
                calls.append(command)
                if len(calls) in (3, 4):
                    self.assertEqual(env.get('ARIADNE_TARGET_DIAGNOSTICS'), '1')
                    diagnostic_envs.append((env['ARIADNE_TARGET_DIAGNOSTICS'], env['ARIADNE_BAP_CORE_DIR']))
                else:
                    self.assertNotIn('ARIADNE_TARGET_DIAGNOSTICS', env)
                result = self.runtime_result(command, cwd, passed=len(calls) in (1, 3))
                if len(calls) == 4:
                    result.stdout = 'resolver target arithmetic\n' + result.stdout
                return result
            with (patch.object(campaign, 'native_build', side_effect=build),
                  patch.dict(campaign.os.environ, {}, clear=True)):
                self.run_fixture_campaign(root, output, observe, native=True)
            report = json.loads((output / 'report.json').read_text())
            self.assertTrue(report['passed'])
            self.assertEqual(observed_builds, ['control-build', 'build'])
            self.assertEqual(len(diagnostic_envs), 2)
            self.assertTrue(diagnostic_envs[0][1].endswith('/control-helper'))
            self.assertTrue(diagnostic_envs[1][1].endswith('/helper'))
            native = report['mutants'][-1]
            self.assertEqual(native['source_file'], 'native/bap-core/legacy_capture.ml')
            self.assertEqual(native['profile_binding']['source_file'], native['source_file'])
            self.assertEqual(native['helper_manifest']['handshake']['source_hashes']['legacy_capture.ml'],
                             native['mutated_source_sha256'])
            self.assertEqual(capture.read_bytes(), capture_bytes)
            self.assertEqual(legacy.read_bytes(), legacy_bytes)

    def test_helper_manifest_binds_compiled_units_and_actual_executable(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sources, helper = root / 'sources', root / 'helper'
            sources.mkdir()
            helper.mkdir()
            for name in campaign.NATIVE_HELPER_SOURCES:
                (sources / name).write_text(name)
            (sources / 'sdk_smoke.ml').write_text('separate SDK smoke check')
            executable = helper / 'ariadne-bap-core'
            executable.write_text('actual executable')
            manifest = {'handshake': {'source_hashes': {
                name: campaign.sha(sources / name) for name in campaign.NATIVE_HELPER_SOURCES}},
                'helper_sha256': campaign.sha(executable)}
            (helper / 'manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(campaign.checked_helper(helper, sources), manifest)
            executable.write_text('another executable')
            with self.assertRaisesRegex(SystemExit, 'native helper identity'):
                campaign.checked_helper(helper, sources)
            executable.write_text('actual executable')
            (sources / 'capture.ml').write_text('mutated source')
            with self.assertRaisesRegex(SystemExit, 'native helper identity'):
                campaign.checked_helper(helper, sources)

    def test_compile_failure_or_timeout_cannot_earn_mutant_credit(self):
        for mode in ('compile', 'timeout'):
            with self.subTest(mode=mode), TemporaryDirectory() as directory:
                root = self.make_repo(directory)
                output = Path(directory) / 'campaign'
                calls = []
                def observe(command, cwd, env):
                    calls.append(command)
                    if len(calls) == 1:
                        return self.runtime_result(command, cwd, passed=True)
                    return SimpleNamespace(returncode=101 if mode == 'compile' else None,
                                           stdout='error: could not compile ariadne',
                                           timed_out=mode == 'timeout')
                with self.assertRaisesRegex(SystemExit, 'mutant escaped'):
                    self.run_fixture_campaign(root, output, observe)
                report = json.loads((output / 'report.json').read_text())
                self.assertFalse(report['passed'])
                self.assertFalse(report['mutants'][0]['detected'])
                self.assertFalse(report['mutants'][0]['test_binaries'])

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
        helper_sources = {name: 'a' * 64 for name in campaign.NATIVE_HELPER_SOURCES}
        baseline = {'native/bap-core/' + name: digest for name, digest in helper_sources.items()}
        row = {
            'name': name, **failure_evidence(result, ['expected_test'], control, diagnostic),
            'returncode': 101, 'log_sha256': digest(result.stdout), 'test_binaries': {'sut': 'b' * 64},
            'source_file': 'native/bap-core/legacy_capture.ml',
            'control': {**control_evidence(control, ['expected_test']), 'returncode': 0,
                        'log_sha256': digest(control.stdout), 'source_sha256': 'a' * 64,
                        'test_binaries': {'control': 'c' * 64},
                        'helper_manifest': {'handshake': {'source_hashes': helper_sources}}},
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
