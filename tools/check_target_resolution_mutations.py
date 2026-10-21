#!/usr/bin/env python3
"""Isolated real-code mutations for the captured indirect-target resolver."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


INPUT_TREES = ('src', 'tests', 'native', 'Specs', 'tools', 'mbt')
FIXTURE_TREES = ('evidence/Ariadne/indirect-target-resolution/dump048B-20261012',)
IGNORED_PARTS = {'__pycache__', 'target'}
TIMEOUT_SECONDS = 1200
# Production helper translation units; sdk_smoke.ml is a separate SDK check.
NATIVE_HELPER_SOURCES = (
    'recovery.ml', 'dense_completion.ml', 'stateflow.ml', 'terminal.ml', 'legacy_capture.ml',
    'capture.ml', 'legacy_guard.ml', 'guard.ml', 'legacy_composition.ml', 'loop_closure.ml',
    'legacy_composition_v2.ml', 'composition.ml', 'project_state.ml', 'main.ml',
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def source_inventory(root=None):
    """Re-enumerate input names as well as bytes, including generated bindings."""
    root = ROOT if root is None else root
    files = [p for tree in INPUT_TREES + FIXTURE_TREES for p in (root / tree).rglob('*')
             if p.is_file() and not IGNORED_PARTS.intersection(p.relative_to(root).parts)]
    files.extend(p for p in (root / 'Cargo.toml', root / 'Cargo.lock') if p.is_file())
    return {str(p.relative_to(root)): sha(p) for p in sorted(set(files))}


def copy_inputs(checkout, baseline):
    for tree in INPUT_TREES + FIXTURE_TREES:
        if (ROOT / tree).is_dir():
            shutil.copytree(ROOT / tree, checkout / tree,
                            ignore=shutil.ignore_patterns(*sorted(IGNORED_PARTS)))
    for name in ('Cargo.toml', 'Cargo.lock'):
        shutil.copyfile(ROOT / name, checkout / name)
    # Check byte identity before the task-local dependency path rewrite.
    if source_inventory(checkout) != baseline:
        raise SystemExit('copied qualification inputs differ from baseline')
    manifest = checkout / 'Cargo.toml'
    original = manifest.read_text()
    marker = 'path = "../MirrorRust"'
    if original.count(marker) != 1:
        raise SystemExit('MirrorRust dependency path seam is not unique')
    manifest.write_text(original.replace(marker, 'path = ' + json.dumps(str(ROOT.parent / 'MirrorRust')), 1))
    return manifest


def write_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def write_report(output, records, baseline, expected, final_sources=None, passed=False, failure=None):
    stable = final_sources is not None and baseline == final_sources
    names = [row['name'] for row in records]
    complete = (stable and len(names) == len(set(names)) and set(names) == set(expected)
                and all(row.get('detected') for row in records))
    if passed and not complete:
        raise SystemExit('incomplete or unstable mutation campaign cannot pass')
    report = {'schema': 'ariadne.target-resolution-mutations/v2', 'mutants': records,
              'passed': passed and complete, 'complete': passed and complete,
              'expected_mutants': sorted(expected), 'baseline_sources': baseline,
              'sources_unchanged': stable, 'compile_failures_credited': False,
              'positive_controls_required': True,
              'source_sha256': baseline.get('src/bap/target_resolution.rs')}
    if final_sources is not None:
        report['final_sources'] = final_sources
        report['source_changes'] = {
            'added': sorted(set(final_sources) - set(baseline)),
            'removed': sorted(set(baseline) - set(final_sources)),
            'changed': sorted(name for name in set(baseline) & set(final_sources)
                              if baseline[name] != final_sources[name]),
        }
    if failure is not None:
        report['failure'] = failure
    write_json(output / 'report.json', report)
    return report


def command_result(code, stdout, stderr, timed_out):
    """Append diagnostics after stdout so a child cannot split a libtest line."""
    stdout, stderr = stdout or '', stderr or ''
    combined = stdout
    if stderr:
        combined += '\n--- command stderr (captured separately) ---\n' + stderr
    return SimpleNamespace(returncode=code, stdout=combined, timed_out=timed_out,
                           captured_stdout=stdout, captured_stderr=stderr)


def run_command(command, cwd, env=None, timeout=TIMEOUT_SECONDS):
    """Capture streams independently and stop the whole process group on timeout."""
    process = subprocess.Popen(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_process_group(process)
        stdout, stderr = process.communicate()
        return command_result(None, stdout, stderr, timed_out=True)
    except BaseException:
        stop_process_group(process)
        process.communicate()
        raise
    return command_result(process.returncode, stdout, stderr, timed_out=False)


def command_logs(directory, label, result):
    """Retain verbatim streams as well as the post-completion observer log."""
    log = directory / (label + '.log')
    log.write_text(result.stdout)
    streams = {}
    for name, text in [('stdout', getattr(result, 'captured_stdout', result.stdout)),
                       ('stderr', getattr(result, 'captured_stderr', ''))]:
        path = directory / (label + '.' + name + '.log')
        path.write_text(text)
        streams[name] = {'path': path.name, 'sha256': sha(path)}
    return {'log_sha256': sha(log), 'output_streams': streams,
            'stderr_combined_after_completion': True}


def stop_process_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # The immediate child can exit before a compiler descendant. Reap any
    # remaining members even after wait() observes the child exit.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


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
        ('no-graph-binding', source, '|| report.graph_sha256 != report_graph_digest(report, instructions, roots)?', '|| false', None),
        ('subtract-relative-offset', source, 'base.wrapping_add(i32::from_le_bytes(', 'base.wrapping_sub(i32::from_le_bytes(', producer),
        ('seed-becomes-root', materialize, 'let mut pending = query.entry_points.clone();', 'let mut pending = query.entry_points.union(&query.slice_seeds).copied().collect::<AddressSet>();', None),
        ('discard-incoming-alternative', source, bypass.group(), '/* deliberately drop the unresolved incoming state */', producer),
        ('wrong-table-scale', source, 'index.wrapping_mul(4)', 'index.wrapping_mul(8)', producer),
        ('ignored-guard', source, 'if roots.contains(&cursor) || frontier {', 'if roots.contains(&cursor) || frontier { let guards = if roots.contains(&cursor) { Vec::<Guard>::new() } else { guards.clone() };', producer),
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


def binary_identities(build, stdout):
    """Bind only executables Cargo reported for this invocation, never stale files."""
    binaries = {}
    for line in stdout.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or record.get('reason') != 'compiler-artifact':
            continue
        executable = record.get('executable')
        if executable is None:
            continue
        path = Path(executable)
        if not path.resolve().is_relative_to(build.resolve()) or not path.is_file():
            raise SystemExit('compiler executable is missing or outside its isolated build')
        binaries[str(path.relative_to(build))] = sha(path)
    return binaries


def qualified_test(name):
    input_tests = {
        'both_platforms_expand_targets_without_promoting_seeds_to_roots',
        'prepared_target_resolution_rejects_changed_semantic_source',
        'captured_table_targets_remain_edges_when_destination_code_is_missing',
        *NATIVE_MUTATION_TESTS.values(),
    }
    prefix = ('input::materialize::target_resolution_tests::' if name in input_tests
              else 'bap::target_resolution::tests::')
    return prefix + name


def cargo_command(manifest, build, test, ignored=False):
    command = ['cargo', 'test', '--offline', '--locked', '-j', '1', '--message-format=json',
               '--manifest-path', str(manifest), '--target-dir', str(build), '--lib',
               qualified_test(test), '--', '--exact', '--nocapture', '--test-threads=1']
    if ignored:
        command.append('--ignored')
    return command


def run_control(directory, command, cwd, env, expected, build, source_sha256, helper_manifest=None):
    """A prerequisite failure aborts the campaign before the source is mutated."""
    result = run_command(command, cwd, env)
    logs = command_logs(directory, 'control', result)
    record = {**control_evidence(result, expected), 'returncode': result.returncode,
              'timed_out': result.timed_out, 'command': command, **logs,
              'test_binaries': binary_identities(build, result.stdout),
              'source_sha256': source_sha256}
    if helper_manifest is not None:
        record['helper_manifest'] = helper_manifest
    write_json(directory / 'control.json', record)
    if not record['passed'] or not record['test_binaries']:
        raise SystemExit('unmodified control did not pass its expected runtime test: ' + ', '.join(expected))
    return result, record


def native_mutation_spec():
    return ('native-unsigned-offset', 'native/bap-core/legacy_capture.ml',
            'Int64.add base (signed raw 32)', 'Int64.add base raw', None)


def native_observer_binding():
    """Fail preflight if the selected observer no longer exercises the legacy profile.

    This is a source routing check; only the compiled arithmetic failure earns
    mutation credit. The source inventory binds every checked routing input.
    """
    test_file = ROOT / 'tests/input/target_resolution_unit.rs'
    test = NATIVE_MUTATION_TESTS['native-unsigned-offset']
    observer = re.search(r'fn ' + re.escape(test) + r'\(\)\s*\{(.*?)(?=\n#\[test\]|\Z)',
                         test_file.read_text(), re.DOTALL)
    calls = re.findall(r'\.(prepare_with_bap_[A-Za-z0-9_]+)\(', observer.group(1)) if observer else []
    if calls != ['prepare_with_bap_target_resolution']:
        raise SystemExit('native mutation observer preparation/profile changed')
    router = ROOT / 'native/bap-core/capture.ml'
    route = re.search(
        r'let admit_resolved \?loop_checker j snapshot =\s*'
        r'let report=get j "target_resolution" in\s*'
        r'if string report "schema"="([^"\n]+)" then\s*'
        r'admit_resolved_current ~loop_checker j snapshot\s*'
        r'else ([A-Za-z_]+)\.admit_resolved j snapshot', router.read_text())
    if not route or route.group(1) != 'ariadne.indirect-target-resolution/v3':
        raise SystemExit('native mutation profile dispatch changed')
    file = 'native/bap-core/' + route.group(2).lower() + '.ml'
    if file != native_mutation_spec()[1]:
        raise SystemExit('native mutation translation unit does not match observer profile dispatch')
    legacy = (ROOT / file).read_text()
    if not re.search(r'string report "schema"="ariadne.indirect-target-resolution/v1"\s*&&\s*'
                     r'string report "profile"="captured-indirect-targets/v1"', legacy):
        raise SystemExit('native mutation legacy admission profile changed')
    return {'observer': qualified_test(test), 'preparation': calls[0],
            'schema': 'ariadne.indirect-target-resolution/v1',
            'profile': 'captured-indirect-targets/v1', 'source_file': file,
            'routing_sources': {str(path.relative_to(ROOT)): sha(path)
                                for path in (test_file, router, ROOT / file)}}


def checked_helper(directory, sources):
    manifest = json.loads((directory / 'manifest.json').read_text())
    expected = {name: sha(sources / name) for name in NATIVE_HELPER_SOURCES}
    if (manifest['handshake']['source_hashes'] != expected
            or manifest['helper_sha256'] != sha(directory / 'ariadne-bap-core')):
        raise SystemExit('native helper identity does not bind the selected sources and executable')
    return manifest


def native_build(directory, sources, output, label, env):
    command = ['python3', str(ROOT / 'native/bap-core/build.py'), '--source-dir', str(sources),
               '--output', str(output)]
    result = run_command(command, ROOT, env)
    logs = command_logs(directory, label, result)
    write_json(directory / (label + '.json'), {'command': command, 'returncode': result.returncode,
                                            'timed_out': result.timed_out, **logs})
    if result.returncode != 0:
        raise SystemExit('native ' + label + ' failed or timed out')
    return checked_helper(output, sources)


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
    for name, file, before, after, scope in mutations + [native_mutation_spec()]:
        apply_mutation((ROOT / file).read_text(), name, before, after, scope)
    native_binding = native_observer_binding() if args.native or args.check_seams else None
    if args.check_seams:
        print(json.dumps({'rust': RUST_MUTATION_TESTS, 'native': NATIVE_MUTATION_TESTS,
                          'native_observer_binding': native_binding}, indent=2))
        return
    if args.output is None:
        parser.error('--output is required unless --check-seams is selected')
    output = args.output.resolve()
    if args.native and not output.is_relative_to(ROOT / 'target'):
        parser.error('--native needs task-owned output beneath the root target/ directory')
    output.mkdir(parents=True, exist_ok=False)
    records, baseline, final_sources = [], {}, None
    expected_names = set(RUST_MUTATION_TESTS) | (set(NATIVE_MUTATION_TESTS) if args.native else set())
    write_report(output, records, baseline, expected_names)
    env = dict(os.environ, CARGO_BUILD_JOBS='1', RUST_TEST_THREADS='1')
    try:
        baseline = source_inventory()
        write_json(output / 'source-inventory.json', baseline)
        write_report(output, records, baseline, expected_names)
        for name, file, before, after, scope in mutations:
            directory = output / name
            checkout = directory / 'sut'
            checkout.mkdir(parents=True)
            manifest = copy_inputs(checkout, baseline)
            target = checkout / file
            original = target.read_text()
            build_directory = directory / 'build'
            expected = [RUST_MUTATION_TESTS[name]]
            command = cargo_command(manifest, build_directory, expected[0])
            record = {'name': name, 'source_file': file, 'detected': False}
            records.append(record)
            print('CONTROL ' + name, flush=True)
            control, control_record = run_control(directory, command, checkout, env, expected,
                                                 build_directory, sha(target))
            record['control'] = control_record
            write_report(output, records, baseline, expected_names)
            target.write_text(apply_mutation(original, name, before, after, scope))
            print('MUTANT ' + name, flush=True)
            started = time.monotonic()
            result = run_command(command, checkout, env)
            logs = command_logs(directory, 'test', result)
            observation = failure_evidence(result, expected, control)
            record.update({**observation, 'returncode': result.returncode, 'timed_out': result.timed_out,
                           'seconds': time.monotonic() - started, 'mutated_source_sha256': sha(target),
                           **logs, 'command': command,
                           'test_binaries': binary_identities(build_directory, result.stdout)})
            # A stale control executable cannot qualify a Rust source mutation.
            changed_executable = record['test_binaries'] != control_record['test_binaries']
            record['mutant_executable_changed'] = changed_executable
            record['detected'] &= bool(record['test_binaries']) and changed_executable
            write_json(directory / 'result.json', record)
            write_report(output, records, baseline, expected_names)
            print(json.dumps(record), flush=True)
            if not record['detected']:
                raise SystemExit('mutant escaped, failed to compile, or missed its expected test: ' + name)
            if args.discard_builds:
                shutil.rmtree(build_directory)
        if args.native:
            name, file, before, after, scope = native_mutation_spec()
            directory = output / name
            sources = directory / 'sources'
            shutil.copytree(ROOT / 'native/bap-core', sources,
                            ignore=shutil.ignore_patterns(*sorted(IGNORED_PARTS)))
            source_file = sources / Path(file).name
            if {str(path.relative_to(sources)): sha(path) for path in sources.rglob('*') if path.is_file()} != {
                    path.removeprefix('native/bap-core/'): digest for path, digest in baseline.items()
                    if path.startswith('native/bap-core/')}:
                raise SystemExit('copied native helper inputs differ from baseline')
            original = source_file.read_text()
            record = {'name': name, 'source_file': file, 'detected': False,
                      'profile_binding': native_binding}
            records.append(record)
            control_helper = directory / 'control-helper'
            control_manifest = native_build(directory, sources, control_helper, 'control-build', env)
            control_env = dict(env, ARIADNE_BAP_CORE_DIR=str(control_helper),
                               ARIADNE_TARGET_DIAGNOSTICS='1')
            build_directory = directory / 'build'
            expected = [NATIVE_MUTATION_TESTS[name]]
            command = cargo_command(ROOT / 'Cargo.toml', build_directory, expected[0], ignored=True)
            print('CONTROL ' + name, flush=True)
            control, control_record = run_control(directory, command, ROOT, control_env, expected,
                                                 build_directory, sha(source_file), control_manifest)
            record['control'] = control_record
            write_report(output, records, baseline, expected_names)
            source_file.write_text(apply_mutation(original, name, before, after, scope))
            helper = directory / 'helper'
            mutant_manifest = native_build(directory, sources, helper, 'build', env)
            if mutant_manifest['helper_sha256'] == control_manifest['helper_sha256']:
                raise SystemExit('native mutation did not change its compiled helper')
            mutant_env = dict(env, ARIADNE_BAP_CORE_DIR=str(helper),
                              ARIADNE_TARGET_DIAGNOSTICS='1')
            print('MUTANT ' + name, flush=True)
            started = time.monotonic()
            result = run_command(command, ROOT, mutant_env)
            logs = command_logs(directory, 'test', result)
            observation = failure_evidence(result, expected, control, NATIVE_MUTATION_DIAGNOSTICS[name])
            record.update({**observation, 'returncode': result.returncode, 'timed_out': result.timed_out,
                           'seconds': time.monotonic() - started,
                           'mutated_source_sha256': sha(source_file), **logs,
                           'helper_manifest': mutant_manifest, 'command': command,
                           'test_binaries': binary_identities(build_directory, result.stdout)})
            record['detected'] &= bool(record['test_binaries'])
            write_json(directory / 'result.json', record)
            write_report(output, records, baseline, expected_names)
            print(json.dumps(record), flush=True)
            if not record['detected']:
                raise SystemExit('native arithmetic mutant escaped or missed its expected test')
            if args.discard_builds:
                shutil.rmtree(build_directory)
        final_sources = source_inventory()
        write_json(output / 'final-source-inventory.json', final_sources)
        if baseline != final_sources:
            raise SystemExit('qualification source changed during mutation campaign')
        write_report(output, records, baseline, expected_names, final_sources, passed=True)
    except BaseException as error:
        # A failed prerequisite, interrupted command or changed source can never
        # leave a stale passing campaign receipt.
        if baseline:
            try:
                final_sources = source_inventory()
            except (OSError, ValueError):
                final_sources = None
        write_report(output, records, baseline, expected_names, final_sources,
                     failure={'type': type(error).__name__, 'message': str(error)})
        raise


if __name__ == '__main__':
    main()
