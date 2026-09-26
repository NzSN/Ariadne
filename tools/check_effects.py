#!/usr/bin/env python3
"""Run the operand/effects acceptance gates and bind results to stable sources."""
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
    for directory in ('src', 'tests', 'native/llvm_mc'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file())
    for pattern in ('Specs/*.tla', 'Specs/*.cfg', 'Specs/check-effects.sh',
                    'tools/check_effects*.py', 'mbt/*.py', 'mbt/src/*.rs'):
        paths.update(ROOT.glob(pattern))
    paths.update(ROOT / p for p in ('Cargo.toml', 'Cargo.lock', 'Specs/AMD64/manuals.lock.json',
                                   'mbt/corpus/manifest.json'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    artifacts = Path(tempfile.mkdtemp(prefix='ariadne-effects-acceptance-'))
    print(f'Acceptance artifacts: {artifacts}', flush=True)
    before = sources()
    env = {**os.environ, 'ARIADNE_LLVM_MC': str(ROOT / 'target/ariadne-llvm-mc')}
    gates = [
        ('rust-tests', ['cargo', 'test', '--offline']),
        ('format', ['cargo', 'fmt', '--all', '--', '--check']),
        ('clippy', ['cargo', 'clippy', '--offline', '--all-targets', '--', '-D', 'warnings']),
        ('native-v1-v2', ['bash', 'native/llvm_mc/check.sh']),
        ('projection', ['bash', 'Specs/check-effects.sh']),
        ('mutations', ['python3', 'tools/check_effects_mutations.py']),
        ('core-mbt', ['python3', 'mbt/run.py']),
        ('measurement', ['cargo', 'test', '--offline', '--test', 'effects',
                         'batched_preparation_preserves_every_record_and_reports_measurement',
                         '--', '--ignored', '--exact', '--nocapture']),
    ]
    results = []
    for name, command in gates:
        start = time.monotonic()
        try:
            run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
            code, output = run.returncode, run.stdout + run.stderr
        except subprocess.TimeoutExpired as error:
            code, output = -1, f'Timed out: {error}'
        log = artifacts / f'{name}.log'
        log.write_text(output)
        results.append({'gate': name, 'command': command, 'exitCode': code,
                        'seconds': round(time.monotonic()-start, 3), 'log': str(log)})
        print(f'{name}: {"PASS" if code == 0 else "FAIL"} ({log})', flush=True)
        # Complete independent gates even after a tool/prerequisite failure.
    stable = before == sources()
    report = {'recordedUtc': datetime.now(timezone.utc).isoformat(), 'sourceSha256': before,
              'sourcesStable': stable, 'gates': results,
              'passed': stable and all(r['exitCode'] == 0 for r in results)}
    (artifacts / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Report: {artifacts / "report.json"}', flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
