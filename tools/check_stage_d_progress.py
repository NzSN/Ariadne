#!/usr/bin/env python3
"""Source-bound first-case Stage D component gate; milestone acceptance is separate."""

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
    paths = set((ROOT / 'Specs').glob('*.tla'))
    paths.update((ROOT / 'Specs').glob('AMD64*.cfg'))
    paths.update((ROOT / 'Specs/AMD64').glob('*.json'))
    paths.update((ROOT / 'lean/AMD64').rglob('*.lean'))
    paths.update(ROOT / name for name in (
        'lean/lean-toolchain', 'lean/lakefile.toml', 'lean/Audit.lean',
        'native/llvm_mc/decode.cpp', 'native/llvm_mc/build.sh'))
    paths.update((ROOT / 'tools').glob('*amd64*.py'))
    paths.update((ROOT / 'tools').glob('check_stage_d*.py'))
    paths.update((ROOT / 'Specs').glob('check-amd64*.sh'))
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def run(command, cwd, env, directory, name, timeout):
    start = time.monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=timeout)
        code, output = result.returncode, result.stdout + result.stderr
    except (subprocess.TimeoutExpired, OSError) as error:
        code, output = -1, repr(error)
    log = directory / f'{name}.log'
    log.write_text(output)
    print(f'{name}: {"PASS" if code == 0 else "FAIL"} ({log})', flush=True)
    return {'gate': name, 'exitCode': code,
            'seconds': round(time.monotonic() - start, 3),
            'command': command, 'log': str(log)}


def main():
    directory = Path(tempfile.mkdtemp(prefix='ariadne-stage-d-progress-'))
    print(f'Stage D artifacts: {directory}', flush=True)
    before = sources()
    env = {**os.environ,
           'ELAN_TOOLCHAIN': os.environ.get('ELAN_TOOLCHAIN', 'ariadne-4.33.1'),
           'AMD64_MANUAL_CACHE': os.environ.get('AMD64_MANUAL_CACHE', '/tmp/ariadne-amd-sources'),
           'ARIADNE_LLVM_MC': str(ROOT / 'target/ariadne-llvm-mc')}
    lean = subprocess.run(['lake', '--version'], cwd=ROOT / 'lean', env=env,
                          capture_output=True, text=True, timeout=30)
    if lean.returncode or 'Lean version 4.33.1' not in lean.stdout:
        raise SystemExit('Pinned Lean 4.33.1 unavailable; no Stage D acceptance')
    gates = [
        ('first-form-observation', ['python3', 'tools/check_stage_d_mov_binding.py',
                                    '--report', str(directory / 'first-form.json')], ROOT, 60),
        ('amd64-components', ['bash', 'Specs/check-amd64.sh'], ROOT, 1800),
        ('first-case-mutations', ['python3', 'tools/check_stage_d_mov_mutations.py'], ROOT, 600),
        ('native-effects-regression', ['cargo', 'test', '--offline', '--locked',
                                       '--test', 'effects', '--', '--ignored'], ROOT, 600),
        ('profile-integrity', ['python3', 'tools/amd64_profile.py', 'check'], ROOT, 60),
    ]
    records = [run(command, cwd, env, directory, name, timeout)
               for name, command, cwd, timeout in gates]
    required = subprocess.run(
        ['python3', 'tools/amd64_profile.py', 'check', '--require-milestone', 'register-core'],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    required_output = required.stdout + required.stderr
    (directory / 'required-register-core.log').write_text(required_output)
    pending = (required.returncode == 1
               and 'Milestone register-core is pending' in required_output
               and '0/49 verified' in required_output)
    stable = before == sources()
    report = {
        'recordedUtc': datetime.now(timezone.utc).isoformat(),
        'sourceSha256': before, 'sourcesStable': stable,
        'manualCache': env['AMD64_MANUAL_CACHE'],
        'leanVersion': lean.stdout.strip(),
        'gates': records,
        'requiredMilestone': {
            'status': 'pending' if pending else 'unexpected-result',
            'exitCode': required.returncode,
            'log': str(directory / 'required-register-core.log'),
        },
        'verifiedRegisterCoreCases': 0,
        'stageDComplete': False,
        'passed': stable and all(row['exitCode'] == 0 for row in records) and pending,
    }
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Report: {directory / "report.json"}', flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
