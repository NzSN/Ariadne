#!/usr/bin/env python3
"""Isolated real-code mutations for the captured indirect-target resolver."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def source_inventory():
    files = [ROOT / 'Cargo.toml', ROOT / 'Cargo.lock', Path(__file__)]
    for folder in ['src', 'tests', 'native/bap-core', 'native/bap']:
        files.extend(p for p in (ROOT / folder).rglob('*')
                     if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts)
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(files))}


RUST_MUTATION_TESTS = {
    'unsigned-offset': 'admitted_capture_dispatch_enumerates_all_45_targets_and_replays_coverage',
    'big-endian-offset': 'admitted_capture_dispatch_enumerates_all_45_targets_and_replays_coverage',
    'unknown-is-complete': 'newly_admitted_guard_bypass_downgrades_coverage_but_preserves_candidates',
    'lost-clobber': 'opaque_call_clobber_does_not_inherit_an_earlier_register_value',
    'no-graph-binding': 'forged_source_expression_premise_and_graph_are_rejected',
    'subtract-relative-offset': 'admitted_capture_dispatch_enumerates_all_45_targets_and_replays_coverage',
    'seed-becomes-root': 'both_platforms_expand_targets_without_promoting_seeds_to_roots',
    'discard-incoming-alternative': 'newly_admitted_guard_bypass_downgrades_coverage_but_preserves_candidates',
    'wrong-table-scale': 'admitted_capture_dispatch_enumerates_all_45_targets_and_replays_coverage',
    'ignored-guard': 'admitted_capture_dispatch_enumerates_all_45_targets_and_replays_coverage',
    'dropped-missing-entry': 'missing_entry_keeps_other_destinations_and_unresolved_alternative',
    'filtered-unavailable-target': 'captured_table_targets_remain_edges_when_destination_code_is_missing',
    'skipped-premise': 'forged_source_expression_premise_and_graph_are_rejected',
    'skipped-source-identity': 'prepared_target_resolution_rejects_changed_semantic_source',
}
NATIVE_MUTATION_TESTS = {
    'native-unsigned-offset': 'actual_bap_lifts_and_native_rust_results_agree_on_both_capture_platforms',
}
NATIVE_MUTATION_DIAGNOSTICS = {
    'native-unsigned-offset': 'resolver target arithmetic',
}


def mutation_specs():
    source = 'src/bap/target_resolution.rs'
    materialize = 'src/input/materialize.rs'
    text = (ROOT / source).read_text()
    producer = ('pub(crate) fn resolve<', 'pub(crate) fn validate(')
    bypass = re.search(r'result\.complete = false;\s*result\s*\.unresolved\s*\.insert\("unsupported-or-unknown-target"\.into\(\)\);', text)
    missing = re.search(r'result\.complete = false;\s*result\.unresolved\.insert\("unavailable-control-data"\.into\(\)\);', text)
    if not bypass or not missing:
        raise SystemExit('incoming/missing-entry mutation seam not found')
    return [
        ('unsigned-offset', source, 'i32::from_le_bytes(', 'u32::from_le_bytes(', producer),
        ('big-endian-offset', source, 'i32::from_le_bytes(', 'i32::from_be_bytes(', producer),
        ('unknown-is-complete', source, 'if !result.unresolved.is_empty() {\n            result.complete = false;\n        }', 'result.complete = true; result.unresolved.clear();', producer),
        ('lost-clobber', source, 'else if clobbered(key, killed)', 'else if false && clobbered(key, killed)', None),
        ('no-graph-binding', source, '|| report.graph_sha256 != graph_digest(instructions, roots)?', '|| false', None),
        ('subtract-relative-offset', source, 'base.wrapping_add(i32::from_le_bytes(', 'base.wrapping_sub(i32::from_le_bytes(', producer),
        ('seed-becomes-root', materialize, 'let mut pending = query.entry_points.clone();', 'let mut pending = query.entry_points.union(&query.slice_seeds).copied().collect::<AddressSet>();', None),
        ('discard-incoming-alternative', source, bypass.group(), '/* deliberately drop the unresolved incoming state */', producer),
        ('wrong-table-scale', source, 'index.wrapping_mul(4)', 'index.wrapping_mul(8)', producer),
        ('ignored-guard', source, 'if roots.contains(&cursor) {', 'if roots.contains(&cursor) { let guards: Vec<Guard> = Vec::new();', producer),
        ('dropped-missing-entry', source, missing.group(), '/* deliberately drop the unavailable-entry residual */', producer),
        ('filtered-unavailable-target', materialize, 'let target = parse_target_address(value)?;', 'let target = parse_target_address(value)?;\n                if snapshot.read_prefix(target, 1)?.bytes.is_empty() { continue; }', None),
        ('skipped-premise', source, '|| report.memory_premise != MEMORY_PREMISE', '|| false', None),
        ('skipped-source-identity', materialize, 'return Err("resolver semantic source mismatch".into());', '/* deliberately skip the reader/semantic source binding */', None),
    ]


def apply_mutation(original, name, before, after, scope=None):
    start, end = 0, len(original)
    if scope:
        if original.count(scope[0]) != 1 or original.count(scope[1]) != 1:
            raise SystemExit('mutation scope not unique: ' + name)
        start, end = original.index(scope[0]), original.index(scope[1])
    region = original[start:end]
    if region.count(before) != 1:
        raise SystemExit('mutation seam not unique: ' + name)
    return original[:start] + region.replace(before, after, 1) + original[end:]


def control_evidence(result, expected):
    passed = sorted(set(re.findall(r'^test ([A-Za-z0-9_:]+) \.\.\. ok$', result.stdout, re.MULTILINE)))
    observed = {name.rsplit('::', 1)[-1] for name in passed}
    valid = (result.returncode == 0 and 'test result: ok.' in result.stdout
             and 'test result: FAILED' not in result.stdout and set(expected) <= observed)
    return {'passed': valid, 'expected_tests': expected, 'passed_tests': passed}


def failure_evidence(result, expected, control=None, diagnostic=None):
    # The final failure-name list is stable with captured output and with
    # --nocapture, where a panic can split the initial test-status line.
    summaries = re.findall(
        r'^failures:\n((?:[ \t]*\n|[ \t]+[A-Za-z0-9_:]+\n)+)(?=test result: FAILED)',
        result.stdout, re.MULTILINE,
    )
    failed = sorted(set(re.findall(r'^[ \t]+([A-Za-z0-9_:]+)$', summaries[-1], re.MULTILINE))) if summaries else []
    observed = {name.rsplit('::', 1)[-1] for name in failed}
    control_passed = control is not None and control_evidence(control, expected)['passed']
    diagnostic_matched = diagnostic is None or diagnostic in result.stdout
    detected = (control_passed and diagnostic_matched and result.returncode == 101
                and 'test result: FAILED' in result.stdout and set(expected) <= observed)
    return {'detected': detected, 'expected_failed_tests': expected, 'failed_tests': failed,
            'control_passed': control_passed, 'expected_diagnostic': diagnostic,
            'diagnostic_matched': diagnostic_matched}


def binary_identities(build):
    """Bind the executable before optionally removing this mutant's build tree."""
    return {str(path.relative_to(build)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((build / 'debug/deps').glob('ariadne-*'))
            if path.is_file() and not path.is_symlink() and os.access(path, os.X_OK)}


def run_control(directory, command, cwd, env, expected, build, source_sha256, helper_manifest=None):
    """A prerequisite failure aborts the campaign before the source is mutated."""
    result = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=600)
    log = directory / 'control.log'
    log.write_text(result.stdout)
    record = {**control_evidence(result, expected), 'returncode': result.returncode,
              'command': command, 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
              'test_binaries': binary_identities(build), 'source_sha256': source_sha256}
    if helper_manifest is not None:
        record['helper_manifest'] = helper_manifest
    (directory / 'control.json').write_text(json.dumps(record, indent=2) + '\n')
    if not record['passed'] or not record['test_binaries']:
        raise SystemExit('unmodified control did not pass its expected runtime test: ' + ', '.join(expected))
    return result, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--discard-builds', action='store_true', help='remove each task-owned build tree after recording executable identities and test evidence')
    parser.add_argument('--check-seams', action='store_true', help='validate unique mutation anchors without building or running campaigns')
    args = parser.parse_args()
    mutations = mutation_specs()
    if {row[0] for row in mutations} != set(RUST_MUTATION_TESTS):
        raise SystemExit('mutation definitions and required test expectations differ')
    for name, file, before, after, scope in mutations:
        apply_mutation((ROOT / file).read_text(), name, before, after, scope)
    if args.check_seams:
        print(json.dumps({'rust': RUST_MUTATION_TESTS, 'native': NATIVE_MUTATION_TESTS}, indent=2))
        return
    if args.output is None:
        parser.error('--output is required unless --check-seams is selected')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    baseline = source_inventory()
    source = 'src/bap/target_resolution.rs'
    records = []
    env = dict(os.environ, CARGO_BUILD_JOBS='4')
    for name, file, before, after, scope in mutations:
        checkout = output / name / 'sut'
        checkout.mkdir(parents=True)
        for folder in ['src', 'tests', 'native/bap', 'native/bap-core']:
            shutil.copytree(ROOT / folder, checkout / folder)
        for file_name in ['Cargo.toml', 'Cargo.lock']:
            shutil.copyfile(ROOT / file_name, checkout / file_name)
        evidence = 'evidence/Ariadne/indirect-target-resolution/dump048B-20261012'
        shutil.copytree(ROOT / evidence, checkout / evidence)
        manifest = checkout / 'Cargo.toml'
        manifest.write_text(manifest.read_text().replace('path = "../MirrorRust"', 'path = "' + str(ROOT.parent / 'MirrorRust') + '"'))
        target = checkout / file
        original = target.read_text()
        build_directory = output / name / 'build'
        expected = [RUST_MUTATION_TESTS[name]]
        control_command = ['cargo', 'test', '--offline', '--locked', '--manifest-path', str(manifest),
                           '--target-dir', str(build_directory), '--lib', expected[0], '--', '--test-threads=1']
        control, control_record = run_control(output / name, control_command, checkout, env,
                                             expected, build_directory, hashlib.sha256(target.read_bytes()).hexdigest())
        target.write_text(apply_mutation(original, name, before, after, scope))
        command = ['cargo', 'test', '--offline', '--locked', '--manifest-path', str(manifest),
                   '--target-dir', str(build_directory), '--lib', 'target_resolution', '--', '--test-threads=1']
        started = time.monotonic()
        result = subprocess.run(command, cwd=checkout, env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=600)
        log = output / name / 'test.log'
        log.write_text(result.stdout)
        observation = failure_evidence(result, expected, control)
        records.append({'name': name, **observation, 'returncode': result.returncode,
                        'seconds': time.monotonic()-started, 'mutated_source_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                        'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(), 'command': command,
                        'test_binaries': binary_identities(build_directory), 'control': control_record,
                        'source_file': file})
        (output / name / 'result.json').write_text(json.dumps(records[-1], indent=2) + '\n')
        print(json.dumps(records[-1]), flush=True)
        if not observation['detected']:
            raise SystemExit('mutant escaped, failed to compile, or missed its expected test: ' + name)
        if not records[-1]['test_binaries']:
            raise SystemExit('mutant test executable identity missing: ' + name)
        if args.discard_builds:
            shutil.rmtree(build_directory)
    if args.native:
        directory = output / 'native-unsigned-offset'
        sources = directory / 'sources'
        shutil.copytree(ROOT / 'native/bap-core', sources)
        source_file = sources / 'capture.ml'
        original = source_file.read_text()
        before = 'Int64.add base (signed raw 32)'
        control_helper = directory / 'control-helper'
        control_build = subprocess.run(['python3', str(ROOT / 'native/bap-core/build.py'), '--source-dir', str(sources), '--output', str(control_helper)], cwd=ROOT, text=True, capture_output=True, timeout=600)
        (directory / 'control-build.log').write_text(control_build.stdout + control_build.stderr)
        if control_build.returncode:
            raise SystemExit('unmodified native helper failed to build')
        control_env = dict(env, ARIADNE_BAP_CORE_DIR=str(control_helper))
        build_directory = directory / 'build'
        expected = [NATIVE_MUTATION_TESTS['native-unsigned-offset']]
        command = ['cargo', 'test', '--offline', '--locked', '--target-dir', str(build_directory), '--lib', expected[0], '--', '--ignored', '--test-threads=1']
        control, control_record = run_control(directory, command, ROOT, control_env, expected,
                                             build_directory, hashlib.sha256(source_file.read_bytes()).hexdigest(),
                                             json.loads((control_helper / 'manifest.json').read_text()))
        source_file.write_text(apply_mutation(original, 'native-unsigned-offset', before, 'Int64.add base raw'))
        helper = directory / 'helper'
        build = subprocess.run(['python3', str(ROOT / 'native/bap-core/build.py'), '--source-dir', str(sources), '--output', str(helper)], cwd=ROOT, text=True, capture_output=True, timeout=600)
        (directory / 'build.log').write_text(build.stdout + build.stderr)
        if build.returncode:
            raise SystemExit('native mutant failed to build')
        mutant_env = dict(env, ARIADNE_BAP_CORE_DIR=str(helper))
        result = subprocess.run(command, cwd=ROOT, env=mutant_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
        (directory / 'test.log').write_text(result.stdout)
        observation = failure_evidence(result, expected, control,
                                       NATIVE_MUTATION_DIAGNOSTICS['native-unsigned-offset'])
        records.append({'name': 'native-unsigned-offset', **observation,
                        'returncode': result.returncode,
                        'mutated_source_sha256': hashlib.sha256(source_file.read_bytes()).hexdigest(),
                        'log_sha256': hashlib.sha256((directory / 'test.log').read_bytes()).hexdigest(),
                        'helper_manifest': json.loads((helper / 'manifest.json').read_text()),
                        'command': command, 'test_binaries': binary_identities(build_directory),
                        'control': control_record, 'source_file': 'native/bap-core/capture.ml'})
        (directory / 'result.json').write_text(json.dumps(records[-1], indent=2) + '\n')
        if not observation['detected']:
            raise SystemExit('native arithmetic mutant escaped or missed its expected test')
        if not records[-1]['test_binaries']:
            raise SystemExit('native mutant test executable identity missing')
        if args.discard_builds:
            shutil.rmtree(build_directory)
    report = {'schema': 'ariadne.target-resolution-mutations/v2', 'mutants': records,
              'passed': all(row['detected'] for row in records),
              'expected_mutants': sorted(set(RUST_MUTATION_TESTS) | (set(NATIVE_MUTATION_TESTS) if args.native else set())),
              'baseline_sources': baseline, 'sources_unchanged': baseline == source_inventory(),
              'source_sha256': hashlib.sha256((ROOT / source).read_bytes()).hexdigest()}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if not report['sources_unchanged']:
        raise SystemExit('qualification source changed during mutation campaign')


if __name__ == '__main__':
    main()
