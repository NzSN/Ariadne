#!/usr/bin/env python3
"""Tiny receipt controls; no native helpers, model tools or archives are opened."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_target_resolution as check


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.record = self.base / 'report.json'
        self.report = {'sources': {}, 'artifacts': {}}

    def artifact(self, name, content):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = content if isinstance(content, bytes) else content.encode()
        path.write_bytes(data)
        self.report['artifacts'][name] = {'bytes': len(data), 'sha256': check.sha(path)}
        return path

    def json_artifact(self, name, value):
        return self.artifact(name, json.dumps(value))

    def rejected(self, function, *args):
        with self.assertRaises(SystemExit):
            function(*args)

    def test_stream_bound_inputs_and_path_escape(self):
        root = self.base / 'repo'
        root.mkdir()
        (root / 'source.rs').write_text('source')
        self.report['sources']['source.rs'] = check.sha(root / 'source.rs')
        item = self.artifact('case/result.json', '{}')
        with patch.object(check, 'ROOT', root):
            check.verify_inputs(self.report, self.record)
            (root / 'source.rs').write_text('changed')
            self.rejected(check.verify_inputs, self.report, self.record)
            (root / 'source.rs').write_text('source')
            item.write_text('[]')
            self.rejected(check.verify_inputs, self.report, self.record)
        self.rejected(check.bound_path, self.base, '../outside.json')
        self.rejected(check.bound_path, self.base, str(item))
        self.rejected(check.artifact_path, self.report, self.record, 'unlisted.json')

    def test_native_build_units_exclude_sdk_smoke(self):
        root = self.base / 'repo'
        build = root / 'native/bap-core/build.py'
        build.parent.mkdir(parents=True)
        build.write_text("def main():\n    sources = ['capture.ml', 'main.ml']\n")
        source = {'native/bap-core/capture.ml': '1' * 64,
                  'native/bap-core/main.ml': '2' * 64,
                  'native/bap-core/sdk_smoke.ml': '3' * 64}
        with patch.object(check, 'ROOT', root):
            self.assertEqual(check.native_sources(source),
                             {'capture.ml': '1' * 64, 'main.ml': '2' * 64})
            del source['native/bap-core/main.ml']
            self.rejected(check.native_sources, source)

    def test_mutation_controls_require_stable_inputs_and_changed_compiled_code(self):
        root = self.base / 'repo'
        build = root / 'native/bap-core/build.py'
        build.parent.mkdir(parents=True)
        build.write_text("def main():\n    sources = ['capture.ml', 'main.ml']\n")
        baseline = {name: '1' * 64 for name in ['src/bap/target_resolution.rs',
                    'native/bap-core/capture.ml', 'native/bap-core/main.ml',
                    'native/bap-core/sdk_smoke.ml']}
        compiled = {'capture.ml': '1' * 64, 'main.ml': '1' * 64}
        rows = []
        expected = check.RUST_MUTATION_TESTS | check.NATIVE_MUTATION_TESTS
        for name, test in expected.items():
            qualified = 'module::' + test
            control_text = f'test {qualified} ... ok\ntest result: ok. 1 passed; 0 failed; 0 ignored;\n'
            diagnostic = check.NATIVE_MUTATION_DIAGNOSTICS.get(name)
            failed_text = ((diagnostic + '\n') if diagnostic else '') + (
                f'failures:\n\n    {qualified}\n\ntest result: FAILED. 0 passed; 1 failed; 0 ignored;\n')
            control_path = self.artifact(name + '/control.log', control_text)
            failure_path = self.artifact(name + '/test.log', failed_text)
            source_file = ('native/bap-core/capture.ml' if name in check.NATIVE_MUTATION_TESTS
                           else 'src/bap/target_resolution.rs')
            control = {'returncode': 0, 'passed': True, 'expected_tests': [test],
                       'passed_tests': [qualified], 'log_sha256': check.sha(control_path),
                       'source_sha256': baseline[source_file], 'timed_out': False,
                       'test_binaries': {'observer': '3' * 64}}
            row = {'name': name, 'source_file': source_file, 'control': control,
                   'expected_failed_tests': [test], 'failed_tests': [qualified],
                   'control_passed': True, 'expected_diagnostic': diagnostic,
                   'diagnostic_matched': True, 'detected': True, 'returncode': 101,
                   'log_sha256': check.sha(failure_path), 'timed_out': False,
                   'mutated_source_sha256': '2' * 64,
                   'mutant_executable_changed': True, 'test_binaries': {'observer': '4' * 64}}
            if name in check.NATIVE_MUTATION_TESTS:
                control['helper_manifest'] = {'handshake': {'source_hashes': compiled},
                                              'helper_sha256': '5' * 64}
                row['helper_manifest'] = {'handshake': {'source_hashes': {**compiled, 'capture.ml': '2' * 64}},
                                          'helper_sha256': '6' * 64}
            rows.append(row)
        mutation = {'schema': 'ariadne.target-resolution-mutations/v2', 'passed': True,
                    'complete': True, 'sources_unchanged': True, 'mutants': rows,
                    'expected_mutants': sorted(expected), 'baseline_sources': baseline,
                    'final_sources': baseline, 'source_changes': {'added': [], 'removed': [], 'changed': []},
                    'compile_failures_credited': False, 'positive_controls_required': True}
        with patch.object(check, 'ROOT', root):
            check.verify_mutation_report(mutation, self.record, strict=True)
            check.verify_mutation_report(mutation, self.record)
            changed = copy.deepcopy(mutation)
            changed['source_changes']['added'] = ['new-source.rs']
            self.rejected(check.verify_mutation_report, changed, self.record, True)
            changed = copy.deepcopy(mutation)
            changed['mutants'][0]['test_binaries'] = changed['mutants'][0]['control']['test_binaries']
            self.rejected(check.verify_mutation_report, changed, self.record, True)
            changed = copy.deepcopy(mutation)
            changed['mutants'][-1]['control']['helper_manifest']['handshake']['source_hashes']['sdk_smoke.ml'] = '1' * 64
            self.rejected(check.verify_mutation_report, changed, self.record, True)

    def test_core_import_requires_unique_behavioral_mutants_before_archive_access(self):
        core = {'schema': 'ariadne.bap-core-mutations/v1', 'passed': True, 'observerHashes': {},
                'mutants': [{'mutation': name} for name in sorted(check.CORE_MUTANTS)]}
        self.rejected(check.verify_core_import, core, {}, self.report, self.record)
        core['mutants'][-1] = core['mutants'][0]
        self.rejected(check.verify_core_import, core, {}, self.report, self.record)

    def test_checks_require_actual_nonzero_test_summaries_and_bound_logs(self):
        rows = []
        tests = {'default', 'core', 'reports', 'bap', 'resolver-native'}
        for name in sorted(check.CHECK_NAMES):
            log = ('test result: ok. 2 passed; 0 failed; 3 ignored;\n' if name in tests
                   else 'ariadne-analysis v0.1.0\n' if name == 'core-dependencies' else 'passed\n')
            path = self.artifact('checks/' + name + '.log', log)
            rows.append({'name': name, 'command': ['recorded-command'], 'status': 'passed',
                         'exit': 0, 'results': [[2, 0, 3]] if name in tests else [],
                         'log_sha256': check.sha(path)})
        checks = {'status': 'passed', 'records': rows}
        check.verify_checks(checks, self.report, self.record)
        forged = copy.deepcopy(checks)
        next(row for row in forged['records'] if row['name'] == 'core')['results'] = [[0, 0, 3]]
        self.rejected(check.verify_checks, forged, self.report, self.record)
        self.rejected(check.verify_checks, {'status': 'passed', 'records': rows[:-1]},
                      self.report, self.record)
        self.artifact('checks/core.log', 'test result: ok. 0 passed; 0 failed; 3 ignored;\n')
        next(row for row in checks['records'] if row['name'] == 'core').update(
            results=[[0, 0, 3]], log_sha256=self.report['artifacts']['checks/core.log']['sha256'])
        self.rejected(check.verify_checks, checks, self.report, self.record)

    def test_model_needs_five_results_and_typecheck_execution(self):
        line = 'Model checking completed. No error has been found.\n'
        path = self.artifact('model/models.log', line * 5)
        self.artifact('model/typecheck.log', 'Type checking successful\n')
        self.report['sources']['Specs/AriadneTargetResolution.tla'] = '1' * 64
        model = {'exit': 0, 'passed': True, 'command': ['check-target-resolution.sh'],
                 'log': 'model/models.log', 'log_sha256': check.sha(path),
                 'typecheck_exit': 0, 'typecheck_command': ['apalache-mc', 'typecheck']}
        model['source_hashes'] = {name: '1' * 64 for name in [
            'AriadneTargetResolution.tla', 'check-target-resolution.sh', 'TargetResolution.cfg',
            'TargetResolutionPartial.cfg', 'TargetResolutionIncoming.cfg',
            'TargetResolutionUntrusted.cfg', 'TargetResolutionZero.cfg']}
        self.report['sources'].update({'Specs/' + name: digest
                                       for name, digest in model['source_hashes'].items()})
        check.verify_model(model, self.report, self.record)
        model['typecheck_exit'] = 1
        self.rejected(check.verify_model, model, self.report, self.record)
        model['typecheck_exit'] = 0
        model['log_sha256'] = check.sha(self.artifact('model/models.log', line * 4))
        self.rejected(check.verify_model, model, self.report, self.record)

    def replay(self):
        sources = {'mbt/corpus/manifest.json': '1' * 64,
                   'mbt/stage-e/corpus/manifest.json': '2' * 64}
        manifest = {'helper_sha256': '3' * 64}
        reports = {name: {'analysisBackend': 'bap', 'gatePassed': True,
                          'observationsDispatched': count, 'matchedObservations': count,
                          'executableSha256': '4' * 64}
                   for name, count in [('core-good', 168), ('machine-state-good', 162),
                                       ('core-wrong-digest', 0), ('machine-state-wrong-digest', 0)]}
        result = {'schema': 'ariadne.bap-core-replay/v1', 'passed': True, 'reports': reports,
                  'helperManifest': manifest, 'coreCorpusSha256': sources['mbt/corpus/manifest.json'],
                  'stateflowCorpusSha256': sources['mbt/stage-e/corpus/manifest.json']}
        return result, manifest, sources

    def test_replay_rejects_dispatched_wrong_digest_and_other_helper(self):
        replay, manifest, sources = self.replay()
        check.verify_replay(replay, manifest, sources)
        self.rejected(check.verify_replay, replay, {'helper_sha256': '5' * 64}, sources)
        replay['reports']['core-wrong-digest']['observationsDispatched'] = 1
        self.rejected(check.verify_replay, replay, manifest, sources)

    def test_cli_timing_uses_recorded_wall_exit_and_all_resolver_passes(self):
        text = ('resolver pass_elapsed_us=12 instructions=1 reads=1 stop=None\n'
                'resolver pass_elapsed_us=1000001 instructions=1 reads=1 stop=None\n'
                '\tElapsed (wall clock) time (h:mm:ss or m:ss): 1:00.01\n\tExit status: 0\n')
        self.assertEqual(check.parse_cli_sample(text),
                         {'elapsed_ms': 60010, 'exit_status': 0, 'resolver_pass_us': [12, 1000001]})
        self.assertEqual(check.parse_cli_sample(text.replace('1:00.01', '1:02:03.45'))['elapsed_ms'],
                         3723450)
        self.rejected(check.parse_cli_sample, text + '\tExit status: 0\n')
        self.rejected(check.parse_cli_sample, 'passed')

    def original(self):
        root = self.base / 'repo'
        oracle_name = 'tests/bap/fixtures/target-resolution-table.json'
        freeze_name = 'evidence/Ariadne/indirect-target-resolution/contract-freeze-20261012.json'
        oracle = {'snapshot_sha256': check.ORIGINAL_SHA256, 'entry_count': 58,
                  'table_base': '0x00007ff64791ef58', 'unique_targets': [str(n) for n in range(45)]}
        freeze = {'limits': {'max_entries': 4096}}
        for name, value in [(oracle_name, oracle), (freeze_name, freeze)]:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
            self.report['sources'][name] = check.sha(path)
        records = [{'backend': backend, 'state_sha256': '1' * 64} for backend in ['bap', 'rust']]
        snapshot = 'minidump-captured-amd64-v1:' + check.ORIGINAL_SHA256
        case = {'dump_sha256': check.ORIGINAL_SHA256, 'native_rust_state_equal': True, 'records': records}
        resolution = {'artifact_sha256': check.ORIGINAL_SHA256, 'snapshot': snapshot,
                      'memory_premise': 'FrozenCapturedControlData', 'limits': freeze['limits'],
                      'resolutions': [{'site': check.ORIGINAL_QUERY['dispatch'],
                                       'targets': oracle['unique_targets'], 'complete': False}]}
        cli = {'identity': {'artifact_sha256': check.ORIGINAL_SHA256, 'snapshot_id': snapshot},
               'question': {'site': check.ORIGINAL_QUERY['seed'], 'memory_access': 0}, 'status': 'partial',
               'assumptions': ['FrozenCapturedControlData: named captured bytes']}
        observer = {'passed': True, **check.ORIGINAL_QUERY, 'artifact_sha256': check.ORIGINAL_SHA256,
                    'artifact_bytes': check.ORIGINAL_BYTES, 'table_base': oracle['table_base'],
                    'entry_count': 58, 'targets': oracle['unique_targets']}
        evidence = {'case': 'original/case.json', 'resolution': 'original/resolution.json',
                    'cli_native': 'original/native.json', 'cli_rust': 'original/rust.json',
                    'observer': 'original/observer.json',
                    'query_identity': 'original/query-identity.json', 'normalized': 'original/normalized.json'}
        normalized = {'snapshot': snapshot, 'entry_points': [check.ORIGINAL_QUERY['entry']],
                      'slice_seeds': [check.ORIGINAL_QUERY['seed']], 'input_kind': 'dump',
                      'trusted_fallback': [], 'file_backed': [], 'locations': [],
                      'addresses': [check.ORIGINAL_QUERY['entry'], check.ORIGINAL_QUERY['seed']],
                      'captured': [check.ORIGINAL_QUERY['entry'], check.ORIGINAL_QUERY['seed']],
                      'decodable': [], 'instructions': []}
        normalized_path = self.json_artifact(evidence['normalized'], normalized)
        cli['identity']['request_sha256'] = check.request_fingerprint(normalized)
        for name in check.CAPTURE_OBSERVER_SOURCES:
            self.report['sources'].setdefault(name, '7' * 64)
        observer['source_sha256'] = {name: self.report['sources'][name]
                                      for name in check.CAPTURE_OBSERVER_SOURCES}
        resolution_path = self.json_artifact(evidence['resolution'], resolution)
        observer['artifacts'] = {'resolution': {'bytes': resolution_path.stat().st_size,
                                               'sha256': check.sha(resolution_path)}}
        self.json_artifact(evidence['query_identity'], {
            'artifact_sha256': check.ORIGINAL_SHA256, 'snapshot_id': snapshot,
            'entry_points': normalized['entry_points'], 'slice_seeds': normalized['slice_seeds'],
            'normalized_request_sha256': check.sha(normalized_path),
            'diagnostic_response_timeout_ms': 60000, 'production_cli_timing_credit': False})
        for key, value in [('case', case), ('resolution', resolution), ('cli_native', cli),
                           ('cli_rust', cli), ('observer', observer)]:
            self.json_artifact(evidence[key], value)
        samples = {}
        for backend in ['native', 'rust']:
            log = self.artifact('original/' + backend + '.log',
                                'resolver pass_elapsed_us=20 instructions=1 reads=1 stop=None\n'
                                'Elapsed (wall clock) time (h:mm:ss or m:ss): 0:59.99\nExit status: 0\n')
            samples[backend] = {'elapsed_ms': 59990, 'exit_status': 0, 'resolver_pass_us': [20],
                                'log': str(log.relative_to(self.base)), 'log_sha256': check.sha(log)}
        original = {'schema': 'ariadne.r6-original-capture/v1', 'passed': True,
                    'artifact_sha256': check.ORIGINAL_SHA256, 'artifact_bytes': check.ORIGINAL_BYTES,
                    **check.ORIGINAL_QUERY, 'memory_premise': 'FrozenCapturedControlData',
                    'limits': freeze['limits'], 'targets': oracle['unique_targets'], 'target_complete': False,
                    'native_rust_state_equal': True, 'native_rust_cli_equal': True,
                    'records': records, 'cli_samples': samples, 'independent_capture': observer,
                    'evidence': evidence}
        return root, original

    def test_original_compares_bound_case_oracle_cli_observer_and_limits(self):
        root, original = self.original()
        with patch.object(check, 'ROOT', root):
            check.verify_original(original, self.report, self.record)
            for field, value in [('artifact_sha256', '0' * 64), ('target_complete', True),
                                 ('targets', original['targets'][:-1]), ('limits', {'max_entries': 8192}),
                                 ('entry', check.ORIGINAL_QUERY['seed'])]:
                forged = copy.deepcopy(original)
                forged[field] = value
                self.rejected(check.verify_original, forged, self.report, self.record)
            changed = copy.deepcopy(original['records'])
            changed[0]['state_sha256'] = '2' * 64
            self.json_artifact(original['evidence']['case'],
                               {'dump_sha256': check.ORIGINAL_SHA256, 'native_rust_state_equal': True,
                                'records': changed})
            self.rejected(check.verify_original, original, self.report, self.record)

    def test_original_rejects_rehashed_over_budget_log(self):
        root, original = self.original()
        log = self.artifact('original/native.log',
                            'resolver pass_elapsed_us=1000001 instructions=1 reads=1 stop=None\n'
                            'Elapsed (wall clock) time (h:mm:ss or m:ss): 1:00.01\nExit status: 0\n')
        original['cli_samples']['native'].update(check.parse_cli_sample(log.read_text()))
        original['cli_samples']['native']['log_sha256'] = check.sha(log)
        with patch.object(check, 'ROOT', root):
            self.rejected(check.verify_original, original, self.report, self.record)

    def test_original_rejects_self_consistently_rehashed_additional_query_root(self):
        root, original = self.original()
        normalized_path = self.base / original['evidence']['normalized']
        normalized = check.read_json(normalized_path)
        normalized['entry_points'].append(check.ORIGINAL_QUERY['seed'])
        self.json_artifact(original['evidence']['normalized'], normalized)
        query = check.read_json(self.base / original['evidence']['query_identity'])
        query['entry_points'] = normalized['entry_points']
        query['normalized_request_sha256'] = check.sha(normalized_path)
        self.json_artifact(original['evidence']['query_identity'], query)
        with patch.object(check, 'ROOT', root):
            self.rejected(check.verify_original, original, self.report, self.record)

    def test_original_rejects_rehashed_stale_raw_resolution_receipt(self):
        root, original = self.original()
        observer = original['independent_capture']
        observer['artifacts']['resolution']['sha256'] = '0' * 64
        self.json_artifact(original['evidence']['observer'], observer)
        with patch.object(check, 'ROOT', root):
            self.rejected(check.verify_original, original, self.report, self.record)

    def test_original_rejects_stale_raw_resolution_size(self):
        root, original = self.original()
        observer = original['independent_capture']
        observer['artifacts']['resolution']['bytes'] += 1
        self.json_artifact(original['evidence']['observer'], observer)
        with patch.object(check, 'ROOT', root):
            self.rejected(check.verify_original, original, self.report, self.record)

    def test_original_rejects_rehashed_stale_observer_source_receipt(self):
        root, original = self.original()
        observer = original['independent_capture']
        observer['source_sha256']['tools/check_target_resolution_capture.py'] = '0' * 64
        self.json_artifact(original['evidence']['observer'], observer)
        with patch.object(check, 'ROOT', root):
            self.rejected(check.verify_original, original, self.report, self.record)

    def test_original_rejects_same_fault_cli_from_different_roots(self):
        root, original = self.original()
        normalized = check.read_json(self.base / original['evidence']['normalized'])
        normalized['entry_points'].append(check.ORIGINAL_QUERY['seed'])
        other_request = check.request_fingerprint(normalized)
        for key in ['cli_native', 'cli_rust']:
            cli = check.read_json(self.base / original['evidence'][key])
            cli['identity']['request_sha256'] = other_request
            self.json_artifact(original['evidence'][key], cli)
        with patch.object(check, 'ROOT', root):
            self.rejected(check.verify_original, original, self.report, self.record)

    def test_v2_has_no_boolean_only_gate_shortcut(self):
        report = {'gates': {name: {'passed': True} for name in
                            ['checks', 'model', 'resolver_mutations', 'replay', 'core_mutations', 'original']}}
        with patch.object(check, 'verify_inputs'):
            with self.assertRaises((SystemExit, KeyError)):
                check.verify_v2(report, self.record)


if __name__ == '__main__':
    unittest.main()
