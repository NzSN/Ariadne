#!/usr/bin/env python3
"""Isolated input mistakes must fail unchanged semantic assertions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    ('wrong-file-offset', 'minidump.rs', 'offset: offset as usize,', 'offset: 0,', 'reader',
     'memory_lists_and_packed_memory64_preserve_virtual_addresses_and_file_offsets'),
    ('memory64-descriptor-stride', 'minidump.rs', '.checked_add(size)', '.checked_add(16)', 'reader',
     'memory_lists_and_packed_memory64_preserve_virtual_addresses_and_file_offsets'),
    ('choose-conflicting-byte', 'address_space.rs', 'if conflict {', 'if false && conflict {', 'reader',
     'adjacent_and_identical_overlaps_compose_but_conflicts_are_localized'),
    ('zero-fill-gap', 'address_space.rs',
     'result.stop = ReadStop::NotCaptured(at);\n                break;',
     'result.bytes.push(0);\n                continue;', 'reader',
     'metadata_and_unknown_streams_never_supply_memory'),
    ('discover-call-only-targets', 'materialize.rs', 'if kind.is_local() &&', 'if true &&', 'native',
     'calls_and_seeds_do_not_discover_callees_but_explicit_roots_do'),
    ('publish-on-budget-exhaustion', 'materialize.rs',
     'return Err(limit("instruction starts", &report));', 'break;', 'native',
     'budgets_fail_without_publishing_partial_requests'),
]


def main():
    artifacts = Path(tempfile.mkdtemp(prefix='ariadne-minidump-mutations-'))
    print(f'Mutation artifacts: {artifacts}', flush=True)
    env = {**os.environ, 'ARIADNE_LLVM_MC': str(Path(os.environ.get('ARIADNE_LLVM_MC', ROOT / 'target/ariadne-llvm-mc')).resolve())}
    reports = []
    for name, file, old, new, suite, test in MUTATIONS:
        # Baseline uses the exact same observer and environment.
        flags = ['--', '--exact'] + (['--ignored'] if suite == 'native' else [])
        base_cmd = ['cargo', 'test', '--offline', '--locked', '--manifest-path', str(ROOT / 'input/Cargo.toml'), '--test', suite, test, *flags]
        good = subprocess.run(base_cmd, env=env, capture_output=True, text=True, timeout=120)
        (artifacts / f'{name}-baseline.log').write_text(good.stdout + good.stderr)
        if good.returncode:
            raise SystemExit(f'Correct implementation failed {test}; no mutation evidence')
        sut = artifacts / name
        sut.mkdir()
        for tree in ('src', 'tests'):
            shutil.copytree(ROOT / tree, sut / tree)
        for file_name in ('Cargo.toml', 'Cargo.lock'):
            shutil.copy2(ROOT / file_name, sut / file_name)
        (sut / 'input').mkdir()
        for tree in ('src', 'tests'):
            shutil.copytree(ROOT / 'input' / tree, sut / 'input' / tree)
        for file_name in ('Cargo.toml', 'Cargo.lock'):
            shutil.copy2(ROOT / 'input' / file_name, sut / 'input' / file_name)
        path = sut / 'input/src' / file
        original = path.read_text()
        if original.count(old) != 1:
            raise SystemExit(f'{name}: mutation anchor is not unique')
        path.write_text(original.replace(old, new))
        cmd = ['cargo', 'test', '--offline', '--locked', '--manifest-path', str(sut / 'input/Cargo.toml'),
               '--target-dir', str(artifacts / 'target'), '--test', suite, test, *flags]
        bad = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=180)
        output = bad.stdout + bad.stderr
        (sut / 'mutation.log').write_text(output)
        killed = (bad.returncode == 101 and f'test {test} ... FAILED' in output
                  and 'assertion' in output and 'could not compile' not in output)
        reports.append({'mutation': name, 'test': test, 'assertionRejected': killed})
        print(f'{name}: {"assertion rejected" if killed else "FAILED gate"}', flush=True)
        if not killed:
            raise SystemExit(f'{name}: did not produce intended assertion failure')
    (artifacts / 'report.json').write_text(json.dumps(reports, indent=2) + '\n')


if __name__ == '__main__':
    main()
