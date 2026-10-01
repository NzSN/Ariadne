#!/usr/bin/env python3
"""Minidump-only acceptance, with stable sources and explicit real-fixture input."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def sources():
    paths = set()
    for directory in ('src', 'tests', 'native/llvm_mc', 'input/src', 'input/tests', 'input/examples', 'reports/src', 'bap/src', 'native/bap'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for pattern in ('Specs/AriadneInput*.tla', 'Specs/Input*.cfg', 'Specs/check-input.sh',
                    'tools/check_minidump*.py'):
        paths.update(ROOT.glob(pattern))
    paths.update(ROOT / p for p in ('Cargo.toml', 'Cargo.lock', 'input/Cargo.toml', 'input/Cargo.lock',
                                   'reports/Cargo.toml', 'reports/Cargo.lock', 'bap/Cargo.toml', 'bap/Cargo.lock',
                                   'Specs/AriadneMachineCommon.tla', 'Specs/AriadneTypes.tla'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    directory = Path(tempfile.mkdtemp(prefix='ariadne-minidump-acceptance-'))
    print(f'Acceptance artifacts: {directory}', flush=True)
    before = sources()
    env = {**os.environ, 'ARIADNE_LLVM_MC': str(ROOT / 'target/ariadne-llvm-mc'), 'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
    # The effects regression gate builds the native helper before input-native tests.
    gates = [
        ('effects-regression', ['python3', 'tools/check_effects.py']),
        ('input-tests', ['cargo', 'test', '--offline', '--locked', '--manifest-path', 'input/Cargo.toml']),
        ('format', ['cargo', 'fmt', '--manifest-path', 'input/Cargo.toml', '--', '--check']),
        ('clippy', ['cargo', 'clippy', '--offline', '--locked', '--manifest-path', 'input/Cargo.toml', '--all-targets', '--', '-D', 'warnings']),
        ('native', ['cargo', 'test', '--offline', '--locked', '--manifest-path', 'input/Cargo.toml', '--test', 'native', '--', '--ignored']),
        ('stage-b-fixtures', ['python3', 'input/tests/fixtures/make_stage_b.py', '--check']),
        ('stage-b-native', ['cargo', 'test', '--offline', '--locked', '--manifest-path', 'input/Cargo.toml', '--test', 'stage_b', '--', '--ignored']),
        ('stage-c-cli', ['cargo', 'test', '--offline', '--locked', '--manifest-path', 'input/Cargo.toml', '--test', 'stage_c', '--', '--ignored']),
        ('real-artifacts', ['cargo', 'test', '--offline', '--locked', '--manifest-path', 'input/Cargo.toml', '--test', 'real_dumps', '--', '--ignored']),
        ('formal-input', ['bash', 'Specs/check-input.sh']),
        ('mutations', ['python3', 'tools/check_minidump_mutations.py']),
    ]
    results = []
    for name, command in gates:
        start = time.monotonic()
        if name == 'real-artifacts' and not env.get('ARIADNE_REAL_DUMPS'):
            code, output = 2, 'ARIADNE_REAL_DUMPS not set; external fixture verification unavailable (not a pass)'
        else:
            try:
                run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
                code, output = run.returncode, run.stdout + run.stderr
            except subprocess.TimeoutExpired as error:
                code, output = -1, f'Timed out: {error}'
        log = directory / f'{name}.log'
        log.write_text(output)
        results.append({'gate': name, 'exitCode': code, 'seconds': round(time.monotonic()-start, 3),
                        'command': command, 'log': str(log)})
        print(f'{name}: {"PASS" if code == 0 else "FAIL"} ({log})', flush=True)
    stable = before == sources()
    report = {'recordedUtc': datetime.now(timezone.utc).isoformat(), 'sourceSha256': before,
              'sourcesStable': stable, 'gates': results, 'passed': stable and all(r['exitCode'] == 0 for r in results)}
    (directory / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Report: {directory / "report.json"}', flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
