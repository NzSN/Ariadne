#!/usr/bin/env python3
"""Verify retained indirect-target qualification against current sources and bytes.

This checks a source-bound receipt. It does not run model/native campaigns or
turn a retained result into fresh qualification for a different corpus.
"""
import argparse
import ast
import gzip
import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

from check_frame_path_capture import request_fingerprint
from check_target_resolution_capture import SOURCE_FILES as CAPTURE_OBSERVER_SOURCES
from check_target_resolution_mutations import (
    NATIVE_MUTATION_DIAGNOSTICS, NATIVE_MUTATION_TESTS, RUST_MUTATION_TESTS,
    control_evidence, failure_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'evidence/Ariadne/indirect-target-resolution/qualification-20261013/report.json'
ORIGINAL_SHA256 = '5fea4ca614706fe0040ed3231efee0edf9ce4004a51d902bb581025b48bade08'
ORIGINAL_BYTES = 1305482568
ORIGINAL_QUERY = {'entry': '0x00007ff640079640', 'seed': '0x00007ff640079670',
                  'dispatch': '0x00007ff64007968b'}
CHECK_NAMES = {'fmt', 'default', 'core', 'reports', 'bap', 'clippy', 'core-dependencies',
               'resolver-native', 'python-controls', 'oracle', 'replay-freshness', 'layout'}
CORE_MUTANTS = {'seed-becomes-root', 'drop-call-edge', 'traverse-call-edge', 'early-completion',
                'possible-write-kills', 'drop-propagation', 'drop-slice-seeds', 'drop-slice-expansion',
                'drop-state-propagation', 'collapse-state-ids', 'drop-incomplete-obligations',
                'drop-terminal-relation'}


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def is_digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def native_sources(sources):
    """Use the production build's translation units, excluding SDK-only smoke code."""
    build = ast.parse((ROOT / 'native/bap-core/build.py').read_text())
    declarations = [node.value for node in ast.walk(build) if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == 'sources'
                            for target in node.targets)]
    require(len(declarations) == 1, 'native translation-unit declaration changed')
    names = ast.literal_eval(declarations[0])
    require(names and len(names) == len(set(names)) and all(
        isinstance(name, str) and Path(name).name == name and name.endswith('.ml')
        for name in names), 'invalid native translation units')
    require(all('native/bap-core/' + name in sources for name in names),
            'compiled native source absent from inventory')
    return {name: sources['native/bap-core/' + name] for name in names}


def bound_path(base, relative):
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(),
            'evidence path must be relative')
    path = (base / relative).resolve()
    require(path.is_relative_to(base.resolve()), 'evidence path escapes root')
    return path


def read_json(path):
    if path.suffix == '.gz':
        with gzip.open(path, 'rt') as source:
            return json.load(source)
    return json.loads(path.read_text())


def verify_mutation_report(mutation, record, strict=False):
    require(mutation.get('schema') == 'ariadne.target-resolution-mutations/v2',
            'resolver mutations need unmodified controls and v2 evidence')
    expected = RUST_MUTATION_TESTS | NATIVE_MUTATION_TESTS
    rows = mutation['mutants']
    names = [row['name'] for row in rows]
    require(mutation['passed'] and mutation['sources_unchanged'], 'resolver mutation campaign changed or failed')
    require(len(names) == len(set(names)) and set(names) == set(expected), 'resolver mutation names differ')
    require(mutation.get('expected_mutants') == sorted(expected), 'resolver mutation expectations differ')
    if strict:
        require(mutation.get('complete') is True
                and mutation.get('final_sources') == mutation['baseline_sources']
                and mutation.get('source_changes') == {'added': [], 'removed': [], 'changed': []}
                and mutation.get('compile_failures_credited') is False
                and mutation.get('positive_controls_required') is True,
                'resolver mutation final inventory/control policy differs')
    for row in rows:
        name = row['name']
        tests = [expected[name]]
        control = row.get('control', {})
        control_log = bound_path(record.parent, name + '/control.log')
        require(sha(control_log) == control.get('log_sha256'),
                'resolver control log differs: ' + name)
        control_result = SimpleNamespace(returncode=control.get('returncode'), stdout=control_log.read_text())
        observed_control = control_evidence(control_result, tests)
        require(control.get('passed') and observed_control['passed']
                and control.get('expected_tests') == tests
                and control.get('passed_tests') == observed_control['passed_tests'],
                'resolver unmodified control did not pass: ' + name)
        source_file = row.get('source_file')
        require(source_file in mutation['baseline_sources']
                and control.get('source_sha256') == mutation['baseline_sources'][source_file],
                'resolver control source differs: ' + name)
        if name in NATIVE_MUTATION_TESTS:
            compiled = native_sources(mutation['baseline_sources'])
            require(control['helper_manifest']['handshake']['source_hashes'] == compiled,
                    'resolver native control helper sources differ')
        require(row.get('expected_failed_tests') == tests, 'resolver mutation expected test differs: ' + name)
        log = bound_path(record.parent, name + '/test.log')
        require(sha(log) == row['log_sha256'], 'resolver mutation log differs: ' + name)
        diagnostic = NATIVE_MUTATION_DIAGNOSTICS.get(name)
        observed = failure_evidence(SimpleNamespace(returncode=row['returncode'], stdout=log.read_text()),
                                    tests, control_result, diagnostic)
        require(row.get('control_passed') and row.get('expected_diagnostic') == diagnostic
                and row.get('diagnostic_matched') == observed['diagnostic_matched'],
                'resolver mutation control or semantic diagnostic differs: ' + name)
        require(row['detected'] and observed['detected'] and row['failed_tests'] == observed['failed_tests'],
                'resolver mutation did not fail its expected test: ' + name)
        for label, binaries in [('mutant', row.get('test_binaries', {})),
                                ('control', control.get('test_binaries', {}))]:
            require(binaries and all(is_digest(value) for value in binaries.values()),
                    'resolver ' + label + ' executable identities missing: ' + name)
        if strict:
            require(control.get('timed_out') is False and row.get('timed_out') is False
                    and is_digest(row.get('mutated_source_sha256'))
                    and row['mutated_source_sha256'] != control['source_sha256'],
                    'resolver mutation source/timeout evidence differs: ' + name)
            if name in NATIVE_MUTATION_TESTS:
                helper = row['helper_manifest']
                expected_sources = native_sources(mutation['baseline_sources'])
                expected_sources[Path(source_file).name] = row['mutated_source_sha256']
                require(helper['handshake']['source_hashes'] == expected_sources
                        and is_digest(helper['helper_sha256'])
                        and helper['helper_sha256'] != control['helper_manifest']['helper_sha256'],
                        'native mutant helper did not change the selected source')
            else:
                require(row.get('mutant_executable_changed') is True
                        and row['test_binaries'] != control['test_binaries'],
                        'Rust mutant executable did not change: ' + name)


def verify_inputs(report, record):
    require(report.get('sources') and report.get('artifacts'), 'qualification inputs missing')
    for name, digest in report['sources'].items():
        path = bound_path(ROOT, name)
        require(is_digest(digest) and sha(path) == digest, 'changed qualification source: ' + name)
    for name, identity in report['artifacts'].items():
        path = bound_path(record.parent, name)
        require(path.stat().st_size == identity['bytes'], 'changed evidence size: ' + name)
        require(is_digest(identity['sha256']) and sha(path) == identity['sha256'],
                'changed evidence bytes: ' + name)


def artifact_path(report, record, relative):
    require(relative in report['artifacts'], 'unbound qualification artifact: ' + str(relative))
    return bound_path(record.parent, relative)


def artifact_json(report, record, relative):
    return read_json(artifact_path(report, record, relative))


def command_present(command):
    return ((isinstance(command, str) and bool(command.strip()))
            or (isinstance(command, list) and bool(command)
                and all(isinstance(part, str) and part for part in command)))


def verify_checks(checks, report, record):
    rows = checks['records']
    names = [row['name'] for row in rows]
    require(checks['status'] == 'passed' and len(names) == len(set(names))
            and set(names) == CHECK_NAMES, 'required check names differ')
    for row in rows:
        name = row['name']
        require(row['status'] == 'passed' and row['exit'] == 0
                and command_present(row['command']), 'check execution failed: ' + name)
        log = artifact_path(report, record, 'checks/' + name + '.log')
        require(sha(log) == row['log_sha256'], 'check log differs: ' + name)
        text = log.read_text()
        if name in {'default', 'core', 'reports', 'bap', 'resolver-native'}:
            observed = [[int(value) for value in group] for group in re.findall(
                r'test result: ok\. (\d+) passed; (\d+) failed; (\d+) ignored;', text)]
            require(observed and row['results'] == observed
                    and sum(group[0] for group in observed) > 0
                    and all(group[1] == 0 for group in observed)
                    and 'test result: FAILED' not in text,
                    'check test observations differ: ' + name)
        if name == 'core-dependencies':
            require(text.strip() and not re.search(r'[├└│]─|^\s+\S', text, re.MULTILINE),
                    'core dependency tree is not dependency-free')


def verify_model(model, report, record):
    require(model.get('passed') is True and model['exit'] == 0
            and command_present(model['command']), 'model command did not pass')
    directory = Path(report.get('gates', {}).get('model', {}).get('result', '.')).parent
    relative_log = str(directory / model['log'])
    log = artifact_path(report, record, relative_log)
    require(sha(log) == model['log_sha256'], 'model log differs')
    require(log.read_text().count('Model checking completed. No error has been found.') == 5,
            'finite model scenario coverage differs')
    typecheck = str(Path(relative_log).with_name('typecheck.log'))
    require(artifact_path(report, record, typecheck).stat().st_size > 0
            and model['typecheck_exit'] == 0 and command_present(model['typecheck_command']),
            'model typecheck execution missing')
    require('Specs/AriadneTargetResolution.tla' in report['sources'], 'model source identity missing')
    model_sources = {'AriadneTargetResolution.tla', 'check-target-resolution.sh',
                     'TargetResolution.cfg', 'TargetResolutionPartial.cfg',
                     'TargetResolutionIncoming.cfg', 'TargetResolutionUntrusted.cfg',
                     'TargetResolutionZero.cfg'}
    require(set(model['source_hashes']) == model_sources and all(
        report['sources'].get('Specs/' + name) == digest
        for name, digest in model['source_hashes'].items()), 'model source/configuration hashes differ')


def verify_replay(replay, manifest, sources):
    require(replay.get('schema') == 'ariadne.bap-core-replay/v1'
            and replay.get('passed') is True and replay['helperManifest'] == manifest,
            'replay helper or status differs')
    expected = {'core-good': 168, 'machine-state-good': 162,
                'core-wrong-digest': 0, 'machine-state-wrong-digest': 0}
    require(set(replay['reports']) == set(expected), 'replay families/modes differ')
    for name, count in expected.items():
        row = replay['reports'][name]
        require(row['analysisBackend'] == 'bap' and row['gatePassed'] is True
                and row['observationsDispatched'] == count
                and is_digest(row['executableSha256']), 'replay observation differs: ' + name)
        if name.endswith('-good'):
            require(row['matchedObservations'] == count, 'replay match count differs: ' + name)
    require(replay['coreCorpusSha256'] == sources['mbt/corpus/manifest.json']
            and replay['stateflowCorpusSha256'] == sources['mbt/stage-e/corpus/manifest.json'],
            'replay corpus identities differ')


def verify_core_import(core, manifest, report, record):
    require(core.get('schema') == 'ariadne.bap-core-mutations/v1' and core.get('passed') is True,
            'core mutation receipt did not pass')
    names = [row['mutation'] for row in core['mutants']]
    require(len(names) == len(set(names)) and set(names) == CORE_MUTANTS,
            'core mutation names differ')
    require(core['observerHashes'], 'core mutation observer identities missing')
    for name, digest in core['observerHashes'].items():
        require(report['sources'].get(name) == digest, 'core mutation observer changed: ' + name)
    for row in core['mutants']:
        require(row['family'] in {'core', 'machine-state'} and row['observations'] > 0
                and isinstance(row['mismatch'], dict) and row['mismatch'].get('action')
                and is_digest(row['sourceSha256']), 'core mutant behavioral evidence missing')
    imported = artifact_json(report, record, 'core-import/verification.json')
    require(imported['schema'] == 'ariadne.r6-core-evidence-import/v1', 'core import schema differs')
    archive = imported['archive']
    old_root = ROOT / 'evidence/Ariadne/caller-semantic-coverage/20261019'
    require(archive['source'] == str((old_root / 'evidence.tar.gz').relative_to(ROOT))
            and archive['sha256'] == '240dd9fafd7cafe78ab531934cf5c122955e4629c46e6b7803794ca75987922d'
            and archive['bytes'] == 21973656, 'core import archive identity differs')
    path = bound_path(ROOT, archive['source'])
    require(path.stat().st_size == archive['bytes'] and sha(path) == archive['sha256'],
            'core import archive bytes differ')
    evidence_path = artifact_path(report, record, imported['evidence_manifest'])
    source_path = artifact_path(report, record, imported['source_manifest'])
    require(sha(evidence_path) == sha(old_root / 'manifest.json')
            and sha(source_path) == sha(old_root / 'source-manifest.json'),
            'core import retained manifests differ')
    evidence = read_json(evidence_path)
    require(evidence['archive_sha256'] == archive['sha256']
            and evidence['archive_bytes'] == archive['bytes'], 'core import archive manifest differs')
    core_path = artifact_path(report, record, report['gates']['core_mutations']['result'])
    for member, path in [
        ('mutations/ordinary/result.json', core_path),
        ('campaign/last-checks/native-replay/result.json',
         artifact_path(report, record, imported['baseline_replay'])),
        ('native/manifest.json', artifact_path(report, record, imported['baseline_native_manifest'])),
        ('sources/source-manifest.json', source_path),
    ]:
        identity = evidence['files'][member]
        require(path.stat().st_size == identity['bytes'] and sha(path) == identity['sha256'],
                'core import extracted member differs: ' + member)
    baseline = read_json(source_path)['files']
    relevant = {name for name in baseline if name.startswith((
        'native/bap-core/', 'src/mbt/core/', 'src/mbt/stage_e/', 'mbt/'))
        and name != 'native/bap-core/README.md'}
    relevant.update(core['observerHashes'])
    relevant.update({'tools/check_bap_core_mutations.py', 'tools/check_bap_core_replay.py'})
    for name in relevant:
        require(report['sources'].get(name) == baseline[name], 'core import source changed: ' + name)
    old_native = artifact_json(report, record, imported['baseline_native_manifest'])
    require(old_native == manifest, 'core import baseline native helper differs')
    verify_replay(artifact_json(report, record, imported['baseline_replay']), old_native, report['sources'])


def parse_cli_sample(text):
    elapsed = re.findall(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*([\d:.]+)', text)
    status = re.findall(r'Exit status:\s*(\d+)', text)
    require(len(elapsed) == 1 and len(status) == 1, 'CLI timing/exit receipt missing or ambiguous')
    parts = elapsed[0].split(':')
    require(len(parts) in {2, 3}, 'CLI elapsed representation differs')
    from decimal import Decimal
    seconds = Decimal(0)
    for part in parts:
        seconds = seconds * 60 + Decimal(part)
    return {'elapsed_ms': int(seconds * 1000), 'exit_status': int(status[0]),
            'resolver_pass_us': [int(value) for value in re.findall(r'resolver pass_elapsed_us=(\d+)', text)]}


def verify_original(original, report, record):
    require(original['schema'] == 'ariadne.r6-original-capture/v1' and original.get('passed') is True,
            'original capture did not pass')
    require(original['artifact_sha256'] == ORIGINAL_SHA256 and original['artifact_bytes'] == ORIGINAL_BYTES,
            'original artifact differs')
    for key, value in ORIGINAL_QUERY.items():
        require(original[key] == value, 'original query differs: ' + key)
    require(original['memory_premise'] == 'FrozenCapturedControlData', 'original memory premise differs')
    oracle_name = 'tests/bap/fixtures/target-resolution-table.json'
    freeze_name = 'evidence/Ariadne/indirect-target-resolution/contract-freeze-20261012.json'
    require(oracle_name in report['sources'] and freeze_name in report['sources'],
            'original oracle/contract source identity missing')
    oracle = read_json(ROOT / oracle_name)
    freeze = read_json(ROOT / freeze_name)
    require(oracle['snapshot_sha256'] == ORIGINAL_SHA256 and oracle['entry_count'] == 58
            and len(oracle['unique_targets']) == 45 and original['targets'] == oracle['unique_targets']
            and original['target_complete'] is False, 'original target oracle/coverage differs')
    require(original['limits'] == freeze['limits'], 'original resolver limits differ')
    evidence = original['evidence']
    query = artifact_json(report, record, evidence['query_identity'])
    normalized_path = artifact_path(report, record, evidence['normalized'])
    normalized = read_json(normalized_path)
    snapshot = 'minidump-captured-amd64-v1:' + ORIGINAL_SHA256
    require(query['artifact_sha256'] == ORIGINAL_SHA256 and query['snapshot_id'] == snapshot
            and query['entry_points'] == [ORIGINAL_QUERY['entry']]
            and query['slice_seeds'] == [ORIGINAL_QUERY['seed']]
            and query['normalized_request_sha256'] == sha(normalized_path)
            and query['diagnostic_response_timeout_ms'] == 60000
            and query['production_cli_timing_credit'] is False,
            'original diagnostic query identity differs')
    require(normalized['snapshot'] == snapshot
            and normalized['entry_points'] == query['entry_points']
            and normalized['slice_seeds'] == query['slice_seeds']
            and normalized['input_kind'] == 'dump'
            and normalized['trusted_fallback'] == [] and normalized['file_backed'] == [],
            'original normalized query/capture policy differs')
    require('tools/check_frame_path_capture.py' in report['sources'],
            'request fingerprint implementation identity missing')
    expected_request = request_fingerprint(normalized)
    case = artifact_json(report, record, evidence['case'])
    require(case['dump_sha256'] == ORIGINAL_SHA256 and case['native_rust_state_equal'] is True
            and original['native_rust_state_equal'] is True and original['records'] == case['records'],
            'original full-state receipt differs')
    rows = case['records']
    require(len(rows) == 2 and {row['backend'] for row in rows} == {'bap', 'rust'}
            and len({row['state_sha256'] for row in rows}) == 1
            and all(is_digest(row['state_sha256']) for row in rows), 'original state parity differs')
    resolution = artifact_json(report, record, evidence['resolution'])
    require(resolution['artifact_sha256'] == ORIGINAL_SHA256 and resolution['snapshot'] == snapshot
            and resolution['memory_premise'] == original['memory_premise']
            and resolution['limits'] == original['limits'], 'original resolution binding differs')
    selected = [row for row in resolution['resolutions'] if row['site'] == ORIGINAL_QUERY['dispatch']]
    require(len(selected) == 1 and selected[0]['targets'] == original['targets']
            and selected[0]['complete'] is False, 'original resolution targets differ')
    native = artifact_json(report, record, evidence['cli_native'])
    rust = artifact_json(report, record, evidence['cli_rust'])
    require(native == rust and original['native_rust_cli_equal'] is True, 'original CLI products differ')
    require(native['identity']['artifact_sha256'] == ORIGINAL_SHA256
            and native['identity']['snapshot_id'] == snapshot
            and native['identity']['request_sha256'] == expected_request
            and native['question']['site'] == ORIGINAL_QUERY['seed']
            and native['question']['memory_access'] == 0 and native['status'] == 'partial',
            'original CLI question/artifact/status differs')
    require(any(assumption.startswith('FrozenCapturedControlData:')
                for assumption in native['assumptions']), 'original CLI memory premise missing')
    require(set(original['cli_samples']) == {'native', 'rust'}, 'original CLI backend samples missing')
    for backend, sample in original['cli_samples'].items():
        log = artifact_path(report, record, sample['log'])
        require(sha(log) == sample['log_sha256'], 'original CLI log differs: ' + backend)
        observed = parse_cli_sample(log.read_text())
        require(all(sample[key] == value for key, value in observed.items()), 'CLI timing observations differ')
        require(observed['exit_status'] == 0 and 0 <= observed['elapsed_ms'] <= 60000,
                'original CLI budget failed')
        require(observed['resolver_pass_us'] and max(observed['resolver_pass_us']) <= 1000000,
                'resolver phase budget failed')
    observer = artifact_json(report, record, evidence['observer'])
    require(observer == original['independent_capture'] and observer.get('passed') is True,
            'original independent capture receipt differs')
    resolution_path = artifact_path(report, record, evidence['resolution'])
    observed_resolution = observer['artifacts']['resolution']
    require(observed_resolution['sha256'] == sha(resolution_path)
            and observed_resolution['bytes'] == resolution_path.stat().st_size,
            'independent capture inspected a different resolution artifact')
    require(set(observer['source_sha256']) == set(CAPTURE_OBSERVER_SOURCES)
            and all(report['sources'].get(name) == digest
                    for name, digest in observer['source_sha256'].items()),
            'independent capture observer/source identities differ')
    for key, value in {**ORIGINAL_QUERY, 'artifact_sha256': ORIGINAL_SHA256,
                       'artifact_bytes': ORIGINAL_BYTES, 'table_base': oracle['table_base'],
                       'entry_count': 58, 'targets': oracle['unique_targets']}.items():
        require(observer[key] == value, 'independent capture scope/oracle differs: ' + key)


def verify_v2(report, record):
    verify_inputs(report, record)
    expected = {'checks', 'model', 'resolver_mutations', 'replay', 'core_mutations', 'original'}
    require(set(report['gates']) == expected, 'aggregate gate names differ')
    gates = {name: artifact_json(report, record, gate['result']) for name, gate in report['gates'].items()}
    verify_checks(gates['checks'], report, record)
    verify_model(gates['model'], report, record)
    manifest = artifact_json(report, record, report['native_manifest'])
    require(manifest['schema'] == 'ariadne.bap-core-build/v1'
            and is_digest(manifest['helper_sha256'])
            and manifest['handshake']['source_hashes'] == native_sources(report['sources']),
            'native helper compiled sources differ')
    mutation_record = artifact_path(report, record, report['gates']['resolver_mutations']['result'])
    mutation = gates['resolver_mutations']
    verify_mutation_report(mutation, mutation_record, strict=True)
    for name, digest in mutation['baseline_sources'].items():
        require(report['sources'].get(name) == digest, 'mutation source differs: ' + name)
    for row in mutation['mutants']:
        for suffix in ['control.log', 'test.log']:
            relative = str(Path(report['gates']['resolver_mutations']['result']).parent / row['name'] / suffix)
            artifact_path(report, record, relative)
    verify_replay(gates['replay'], manifest, report['sources'])
    verify_core_import(gates['core_mutations'], manifest, report, record)
    verify_original(gates['original'], report, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, default=DEFAULT)
    parser.add_argument('--correctness-only', action='store_true', help='verify correctness tiers while explicitly leaving performance acceptance open')
    args = parser.parse_args()
    record = args.record.resolve()
    report = read_json(record)
    if report.get('schema') == 'ariadne.indirect-target-qualification/v2':
        require(not args.correctness_only, 'v2 requires every declared gate including fixed timing criteria')
        verify_v2(report, record)
        print('Indirect-target v2 qualification PASS within the declared finite Windows/explanation-only scope.')
        return
    require(report['schema'] == 'ariadne.indirect-target-qualification/v1', 'wrong qualification schema')
    verify_inputs(report, record)
    failed = [name for name, gate in report['gates'].items() if not gate['passed'] and not (args.correctness_only and name == 'performance')]
    require(not failed, 'required finite-profile gates did not pass: ' + ', '.join(failed))
    model_log = (record.parent / report['gates']['model']['log']).read_text()
    require(model_log.count('Model checking completed. No error has been found.') == 5, 'finite model scenario coverage differs')
    for row in report['cli_samples'].values():
        require(row['resolver_pass_us'] and max(row['resolver_pass_us']) <= report['criteria']['resolver_ms'] * 1000, 'resolver phase budget failed')
    case = read_json(record.parent / report['case']['qualification'])
    require(case['dump_sha256'] == report['case']['dump_sha256'], 'dump identity mismatch')
    require(case['native_rust_state_equal'], 'state parity failed')
    records = case['records']
    require({r['backend'] for r in records} == {'bap', 'rust'}, 'missing case backend')
    require(len({r['state_sha256'] for r in records}) == 1, 'case state digest mismatch')
    for row in records:
        for key, value in report['case']['expected'].items():
            require(row[key] == value, 'case oracle mismatch: ' + key)
    target = read_json(record.parent / report['case']['resolution'])
    dispatch = next(r for r in target['resolutions'] if r['site'] == report['case']['dispatch'])
    require(dispatch['targets'] == report['case']['expected_targets'], 'independent captured table targets differ')
    require(not dispatch['complete'], 'unexpected exhaustive original-capture certificate')
    require(target['artifact_sha256'] == case['dump_sha256'], 'receipt artifact differs')
    for row in report['cli_samples'].values():
        require(row['exit_status'] == 0, 'CLI did not complete')
        if not args.correctness_only:
            require(row['elapsed_ms'] <= report['criteria']['expanded_original_dump_cli_ms'], 'CLI budget failed')
    replay = read_json(record.parent / report['gates']['replay']['result'])
    require(replay['passed'], 'replay result failed')
    require(replay['reports']['core-good']['matchedObservations'] == 168, 'core replay coverage differs')
    require(replay['reports']['machine-state-good']['matchedObservations'] == 162, 'stateflow replay coverage differs')
    for key in ['core-wrong-digest', 'machine-state-wrong-digest']:
        require(replay['reports'][key]['observationsDispatched'] == 0, 'wrong-digest replay dispatched')
    mutation_record = record.parent / report['gates']['resolver_mutations']['result']
    mutation = read_json(mutation_record)
    verify_mutation_report(mutation, mutation_record)
    for name, digest in mutation['baseline_sources'].items():
        require(report['sources'][name] == digest, 'mutation observer/source differs: ' + name)
    core = read_json(record.parent / report['gates']['core_mutations']['result'])
    require(core['passed'] and len(core['mutants']) == 12, 'core mutation coverage differs')
    manifest = read_json(record.parent / report['native_manifest'])
    require(replay['helperManifest'] == manifest, 'replay helper differs from qualified helper')
    for name, digest in manifest['handshake']['source_hashes'].items():
        require(report['sources']['native/bap-core/' + name] == digest, 'native helper source differs: ' + name)
    print('Indirect-target correctness PASS; performance acceptance remains open.' if args.correctness_only else 'Indirect-target qualification PASS: current sources, retained artifacts, finite gates and original-capture oracle.')


if __name__ == '__main__':
    main()
