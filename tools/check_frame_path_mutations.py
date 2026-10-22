#!/usr/bin/env python3
"""Remote compiled frame-path mutations with exact passing observer controls."""
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
MUTANTS = [
    ('np-off-by-one', 'src/investigation/frame_paths.rs', 'result.paths.len() >= q.np - 1', 'result.paths.len() >= q.np', 'strict_np_and_equal_frame_cases_preserve_empty_list_meaning'),
    ('loop-budget-ignored', 'src/investigation/frame_paths.rs', '>= limits.max_node_visits', '> limits.max_node_visits', 'enumerated_paths_match_64_independent_cartesian_oracles'),
    ('forged-completeness', 'src/investigation/frame_paths.rs', 'frontier.is_empty() && !blocked && result.stop_reason.is_empty()', 'frontier.is_empty()', 'every_search_work_and_retention_boundary_stays_explicit'),
    ('lost-call-activation', 'src/investigation/frame_paths.rs', 'frame: frame - 1,', 'frame: frame,', 'strict_np_and_equal_frame_cases_preserve_empty_list_meaning'),
    ('guessed-stack-slot', 'src/investigation/frame_unwind.rs',
     '    } else {\n        let slot = registers["rsp"];\n        (\n            slot,\n            r.stack(slot, lo, hi)?,',
     '    } else {\n        let slot = original["rsp"];\n        (\n            slot,\n            r.stack(slot, lo, hi)?,',
     'captured_allocations_saves_and_frame_pointer_restore_only_valid_registers'),
    ('graph-policy-ignored', 'src/investigation/frame_paths.rs', 'let limits = input.graph_limits.unwrap_or_default();', 'let limits = FramePathGraphLimits::default();', 'explicit_graph_policy_preserves_legacy_replay_and_independent_search_stops'),
]
TREES = ('src', 'tests', 'native', 'Specs', 'tools', 'mbt')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_inventory(root):
    files = [p for tree in TREES for p in (root/tree).rglob('*')
             if p.is_file() and not {'__pycache__', 'target'}.intersection(p.relative_to(root).parts)]
    files += [root/'Cargo.toml', root/'Cargo.lock']
    return {str(p.relative_to(root)): sha(p) for p in sorted(files)}


def write_json(path, value):
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    os.replace(temporary, path)


def write_report(output, records, passed=False, failure=None):
    report = {
        'schema': 'ariadne.frame-path-mutations/v2', 'passed': passed,
        'complete': passed, 'positive_controls_required': True,
        'compile_failures_credited': False, 'records': records,
    }
    if failure is not None:
        report['failure'] = failure
    write_json(output/'report.json', report)


def observe(command, cwd, log):
    start = time.monotonic()
    try:
        p = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, timeout=1200)
        text, code = p.stdout, p.returncode
    except subprocess.TimeoutExpired as error:
        text, code = error.stdout or b'', None
        if isinstance(text, bytes):
            text = text.decode(errors='replace')
    log.write_text(text)
    binaries = {}
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get('reason') == 'compiler-artifact' and row.get('executable'):
            binaries[row['executable']] = sha(row['executable'])
    return {'command': command, 'exit': code, 'seconds': time.monotonic()-start,
            'log_sha256': sha(log), 'executables': binaries}, text


def credited(record, text, test, positive):
    assert record['executables'], 'no compiled observer'
    if positive:
        assert record['exit'] == 0 and f'test {test} ... ok' in text, 'positive control did not pass'
    else:
        assert record['exit'] == 101 and 'panicked at' in text and 'test result: FAILED' in text
        assert re.search(r'^    '+re.escape(test)+r'$', text, re.MULTILINE), 'wrong failing observer'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-seams', action='store_true')
    mode.add_argument('--remote', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    for name, file, before, _, _ in MUTANTS:
        assert (ROOT/file).read_text().count(before) == 1, (name, 'mutation seam changed')
    if args.check_seams:
        print('Frame mutation seams PASS:', len(MUTANTS), 'unique edits; no campaign exercised.')
        return
    if args.output_dir is None:
        parser.error('--remote requires --output-dir')
    output = args.output_dir.resolve()
    assert output.is_relative_to(ROOT/'target'), 'use an isolated target/ campaign directory'
    output.mkdir(parents=True, exist_ok=False)
    records = []
    write_report(output, records)
    try:
        source = source_inventory(ROOT)
        write_json(output/'source-inventory.json', source)
        for name, file, before, after, short_test in MUTANTS:
            case = output/name
            sut = case/'source'
            sut.mkdir(parents=True)
            for tree in TREES:
                shutil.copytree(ROOT/tree, sut/tree, ignore=shutil.ignore_patterns('__pycache__', 'target'))
            for item in ('Cargo.toml', 'Cargo.lock'):
                shutil.copyfile(ROOT/item, sut/item)
            assert source_inventory(sut) == source, 'copied qualification source changed'
            manifest = sut/'Cargo.toml'
            manifest.write_text(manifest.read_text().replace('path = "../MirrorRust"',
                                'path = '+json.dumps(str(ROOT.parent/'MirrorRust'))))
            test = short_test if short_test.startswith('captured_') else 'investigation::frame_paths::tests::'+short_test
            command = ['cargo', 'test', '--offline', '--locked', '-j', '1', '--message-format=json',
                       '--target-dir', str(case/'build')]
            command += ['--test', 'input_frame_paths'] if short_test.startswith('captured_') else ['--lib']
            command += [test, '--', '--exact', '--nocapture', '--test-threads=1']
            record = {'name': name, 'observer': test, 'compiled_behavior_rejected': False}
            records.append(record)
            print('CONTROL', name, flush=True)
            control, text = observe(command, sut, case/'control.log')
            record['control'] = control
            write_report(output, records)
            credited(control, text, test, True)
            path = sut/file
            original = path.read_text()
            assert original.count(before) == 1
            path.write_text(original.replace(before, after, 1))
            record['source_sha256'] = sha(path)
            print('MUTANT', name, flush=True)
            mutant, text = observe(command, sut, case/'mutant.log')
            record['mutant'] = mutant
            write_report(output, records)
            credited(mutant, text, test, False)
            record['compiled_behavior_rejected'] = True
            write_json(case/'result.json', record)
            write_report(output, records)
        final_source = source_inventory(ROOT)
        write_json(output/'final-source-inventory.json', final_source)
        assert source == final_source, 'qualification source changed'
        write_report(output, records, passed=True)
    except BaseException as error:
        write_report(output, records, failure={'type': type(error).__name__, 'message': str(error)})
        raise
    print('Frame mutation PASS:', len(records), 'compiled mutants rejected with passing controls.', flush=True)


if __name__ == '__main__':
    main()
