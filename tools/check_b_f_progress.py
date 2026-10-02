#!/usr/bin/env python3
"""Source-bound B/C/E/F progress gate; D acceptance is observed separately."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from rust_layout import copy_sut, source_files
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / 'Specs'


def sources():
    paths = source_files()
    for directory in ('src', 'tests', 'src/input', 'tests/input', 'src/examples',
                      'src/ir', 'tests/ir', 'native/llvm_mc', 'native/llvm_ir',
                      'src/bench', 'tools'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts)
    for name in ('Cargo.toml', 'Cargo.lock', 'Cargo.toml', 'Cargo.lock',
                 'Cargo.toml', 'Cargo.lock', 'Cargo.toml', 'Cargo.lock',
                 'Specs/Ariadne.tla', 'Specs/AriadneMachineState.tla',
                 'Specs/AriadneMachineStateExample.tla', 'Specs/AriadneMachineCommon.tla',
                 'Specs/AriadneLLVMIR.tla', 'Specs/AriadneLLVMIRExample.tla',
                 'Specs/MachineState.cfg', 'Specs/LLVMIR.cfg'):
        paths.add(ROOT / name)
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def retained_stage_e_status():
    """Report Stage E only from its independently passing, still-current record."""
    path=ROOT / 'docs/Ariadne/stage-e-completion-validation.json'
    try:
        evidence=json.loads(path.read_text())
        if not evidence['passed'] or not evidence['sourcesStable']:
            return 'open or stale retained evidence'
        for relative,digest in evidence['sourceHashes'].items():
            if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:
                return 'open or stale retained evidence'
        return 'passed: finite generated conformance; see stage-e-completion-validation.json'
    except (OSError,ValueError,KeyError):
        return 'open or stale retained evidence'


def main():
    out = Path(tempfile.mkdtemp(prefix='ariadne-b-f-progress-'))
    print(f'Progress artifacts: {out}', flush=True)
    before = sources()
    env = {**os.environ,
           'ARIADNE_LLVM_MC': str(ROOT / 'target/ariadne-llvm-mc'),
           'ARIADNE_LLVM_IR': str(ROOT / 'target/ariadne-llvm-ir')}
    gates = [
        ('minidump-b-c', ['python3', 'tools/check_minidump.py'], ROOT),
        ('llvm-ir-build', ['bash', 'native/llvm_ir/build.sh'], ROOT),
        ('root-tests', ['cargo', 'test', '--no-default-features', '--offline', '--locked'], ROOT),
        ('root-format', ['cargo', 'fmt', '--all', '--', '--check'], ROOT),
        ('root-clippy', ['cargo', 'clippy', '--no-default-features', '--offline', '--locked', '--all-targets', '--', '-D', 'warnings'], ROOT),
        ('ir-tests', ['cargo', 'test', '--no-default-features', '--features', 'ir', '--offline', '--locked', '--manifest-path', 'Cargo.toml'], ROOT),
        ('ir-native', ['cargo', 'test', '--no-default-features', '--features', 'ir', '--offline', '--locked', '--manifest-path', 'Cargo.toml', '--test', 'ir_native', '--', '--ignored'], ROOT),
        ('ir-format', ['cargo', 'fmt', '--manifest-path', 'Cargo.toml', '--', '--check'], ROOT),
        ('ir-clippy', ['cargo', 'clippy', '--no-default-features', '--features', 'ir', '--offline', '--locked', '--manifest-path', 'Cargo.toml', '--all-targets', '--', '-D', 'warnings'], ROOT),
        ('bench-format', ['cargo', 'fmt', '--manifest-path', 'Cargo.toml', '--', '--check'], ROOT),
        ('bench-clippy', ['cargo', 'clippy', '--no-default-features', '--features', 'bench', '--offline', '--locked', '--manifest-path', 'Cargo.toml', '--all-targets', '--', '-D', 'warnings'], ROOT),
        ('machine-type', [env.get('APALACHE_MC', 'apalache-mc'), f'--out-dir={out / "machine-type"}', 'typecheck', 'AriadneMachineState.tla'], SPECS),
        ('ir-type', [env.get('APALACHE_MC', 'apalache-mc'), f'--out-dir={out / "ir-type"}', 'typecheck', 'AriadneLLVMIR.tla'], SPECS),
        ('machine-model', [env.get('APALACHE_MC', 'apalache-mc'), f'--out-dir={out / "machine-model"}', 'check', '--init=Init', '--next=Next', '--inv=Safety', '--length=6', '--no-deadlock', 'AriadneMachineStateExample.tla'], SPECS),
        ('ir-model', [env.get('APALACHE_MC', 'apalache-mc'), f'--out-dir={out / "ir-model"}', 'check', '--init=Init', '--next=Next', '--inv=Safety', '--length=8', '--no-deadlock', 'AriadneLLVMIRExample.tla'], SPECS),
        ('machine-tlc', [env.get('TLC', 'tlc'), '-workers', '1', '-metadir', str(out / 'machine-tlc'), '-config', 'MachineState.cfg', 'AriadneMachineStateExample.tla'], SPECS),
        ('ir-tlc', [env.get('TLC', 'tlc'), '-workers', '1', '-metadir', str(out / 'ir-tlc'), '-config', 'LLVMIR.cfg', 'AriadneLLVMIRExample.tla'], SPECS),
        ('profile-integrity', ['python3', 'tools/amd64_profile.py', 'check'], ROOT),
        ('benchmark', ['cargo', 'run', '--no-default-features', '--features', 'bench', '--offline', '--locked', '--manifest-path', 'Cargo.toml', '--release', '--bin', 'ariadne-bench', '--', '128', '3', 'minidump'], ROOT),
    ]
    records = []
    for name, command, cwd in gates:
        start = time.monotonic()
        try:
            run = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                 text=True, timeout=900)
            code, output = run.returncode, run.stdout + run.stderr
            if name == 'benchmark' and code == 0:
                (out / 'benchmark.csv').write_text(run.stdout)
        except (subprocess.TimeoutExpired, OSError) as error:
            code, output = -1, repr(error)
        log = out / f'{name}.log'
        log.write_text(output)
        records.append({'gate': name, 'exitCode': code,
                        'seconds': round(time.monotonic() - start, 3),
                        'command': command, 'log': str(log)})
        print(f'{name}: {"PASS" if code == 0 else "FAIL"} ({log})', flush=True)
    required = subprocess.run(
        ['python3', 'tools/amd64_profile.py', 'check', '--require-milestone', 'register-core'],
        cwd=ROOT, env=env, capture_output=True, text=True)
    required_output = required.stdout + required.stderr
    (out / 'register-core-required.log').write_text(required_output)
    expected_pending = (required.returncode == 1
                        and 'Milestone register-core is pending' in required_output
                        and '0/49 verified' in required_output)
    acceptance_status = ('passed' if required.returncode == 0 else
                         'pending' if expected_pending else 'error')
    stable = before == sources()
    report = {
        'recordedUtc': datetime.now(timezone.utc).isoformat(),
        'sourceSha256': before, 'sourcesStable': stable,
        'gates': records,
        'passed': stable and all(r['exitCode'] == 0 for r in records)
                  and acceptance_status != 'error',
        'registerCoreAcceptance': {
            'exitCode': required.returncode,
            'status': acceptance_status,
            'log': str(out / 'register-core-required.log'),
        },
        'rustRefinementProof': 'open',
        'machineStateModelBasedReplay': retained_stage_e_status(),
        'nativeIrModelBasedReplay': retained_stage_e_status(),
    }
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Report: {out / "report.json"}', flush=True)
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
