#!/usr/bin/env python3
"""Verify retained indirect-target qualification against current sources and bytes.

This checks a source-bound receipt. It does not run model/native campaigns or
turn a retained result into fresh qualification for a different corpus.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from check_target_resolution_mutations import (
    NATIVE_MUTATION_DIAGNOSTICS, NATIVE_MUTATION_TESTS, RUST_MUTATION_TESTS,
    control_evidence, failure_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'evidence/Ariadne/indirect-target-resolution/qualification-20261013/report.json'


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def bound_path(base, relative):
    path = (base / relative).resolve()
    require(path.is_relative_to(base.resolve()), 'evidence path escapes root')
    return path


def read_json(path):
    if path.suffix == '.gz':
        with gzip.open(path, 'rt') as source:
            return json.load(source)
    return json.loads(path.read_text())


def verify_mutation_report(mutation, record):
    require(mutation.get('schema') == 'ariadne.target-resolution-mutations/v2',
            'resolver mutations need unmodified controls and v2 evidence')
    expected = RUST_MUTATION_TESTS | NATIVE_MUTATION_TESTS
    rows = mutation['mutants']
    names = [row['name'] for row in rows]
    require(mutation['passed'] and mutation['sources_unchanged'], 'resolver mutation campaign changed or failed')
    require(len(names) == len(set(names)) and set(names) == set(expected), 'resolver mutation names differ')
    require(mutation.get('expected_mutants') == sorted(expected), 'resolver mutation expectations differ')
    for row in rows:
        name = row['name']
        tests = [expected[name]]
        control = row.get('control', {})
        control_log = bound_path(record.parent, name + '/control.log')
        require(hashlib.sha256(control_log.read_bytes()).hexdigest() == control.get('log_sha256'),
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
            native_sources = {source.removeprefix('native/bap-core/'): digest
                              for source, digest in mutation['baseline_sources'].items()
                              if source.startswith('native/bap-core/') and source.endswith('.ml')}
            require(native_sources and control['helper_manifest']['handshake']['source_hashes'] == native_sources,
                    'resolver native control helper sources differ')
        require(row.get('expected_failed_tests') == tests, 'resolver mutation expected test differs: ' + name)
        log = bound_path(record.parent, name + '/test.log')
        require(hashlib.sha256(log.read_bytes()).hexdigest() == row['log_sha256'], 'resolver mutation log differs: ' + name)
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
            require(binaries and all(len(value) == 64 and all(c in '0123456789abcdef' for c in value)
                                     for value in binaries.values()),
                    'resolver ' + label + ' executable identities missing: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, default=DEFAULT)
    parser.add_argument('--correctness-only', action='store_true', help='verify correctness tiers while explicitly leaving performance acceptance open')
    args = parser.parse_args()
    record = args.record.resolve()
    report = read_json(record)
    require(report['schema'] == 'ariadne.indirect-target-qualification/v1', 'wrong qualification schema')
    for name, digest in report['sources'].items():
        path = bound_path(ROOT, name)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'changed qualification source: ' + name)
    for name, identity in report['artifacts'].items():
        path = bound_path(record.parent, name)
        require(path.stat().st_size == identity['bytes'], 'changed evidence size: ' + name)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == identity['sha256'], 'changed evidence bytes: ' + name)
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
