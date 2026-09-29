#!/usr/bin/env python3
"""Reject bounded MOV64 sign/boundary defects without changing repository sources."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TLA = ROOT / 'Specs/AMD64RegisterCoreProfileChecks.tla'
LEAN = ROOT / 'lean/AMD64/RegisterCoreProfileChecks.lean'
TLA_PROJECTION = ROOT / 'Specs/AMD64RegisterCoreProjectionChecks.tla'
TLA_FAULT = ROOT / 'Specs/AMD64RegisterCoreFaultChecks.tla'
LEAN_PROJECTION = ROOT / 'lean/AMD64/RegisterCoreProjectionChecks.lean'
CHECK = ROOT / 'tools/check_stage_d_mov_mutations.py'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            timeout=180, env=os.environ.copy())
    output = result.stdout + result.stderr
    log.write_text(output)
    return result.returncode, output


def replace_once(source, old, new, name):
    if source.count(old) != 1:
        raise ValueError(f'mutation anchor changed: {name}')
    return source.replace(old, new)


def main():
    work = Path(tempfile.mkdtemp(prefix='ariadne-stage-d-mov-mutants-'))
    print(f'Mutation artifacts: {work}', flush=True)
    source_hashes = {str(path.relative_to(ROOT)): digest(path)
                     for path in [TLA, LEAN, TLA_PROJECTION, TLA_FAULT,
                                  LEAN_PROJECTION, CHECK]}
    tla_source = TLA.read_text()
    tla_mutations = [
        ('lost-sign-extension',
         'UserMov64After.gpr[0] = Base!OneBits(64)',
         'UserMov64After.gpr[0] = Base!ZeroBits(64)'),
        ('wrong-next-ip',
         'UserMov64NextIP == Base!Word({1,2,3})',
         'UserMov64NextIP == Base!Word({1,3})'),
        ('wrong-destination',
         'WriteGPR(UserMov64Before, Base!GPRRef(0, "full64"),',
         'WriteGPR(UserMov64Before, Base!GPRRef(1, "full64"),'),
    ]
    results = []
    for name, old, new in tla_mutations:
        directory = work / name
        directory.mkdir()
        for path in (ROOT / 'Specs').glob('*.tla'):
            shutil.copy2(path, directory / path.name)
        shutil.copy2(ROOT / 'Specs/AMD64RegisterCoreProfileChecks.cfg', directory)
        (directory / TLA.name).write_text(replace_once(tla_source, old, new, name))
        command = [os.environ.get('TLC', 'tlc'), '-workers', '1',
                   '-metadir', str(directory / 'states'), '-config',
                   'AMD64RegisterCoreProfileChecks.cfg', TLA.name]
        code, output = run(command, directory, directory / 'check.log')
        if code == 0 or 'Invariant Safety is violated' not in output:
            raise ValueError(f'{name}: intended TLC safety rejection absent; {directory / "check.log"}')
        results.append({'name': name, 'kind': 'tlc-invariant',
                        'command': command, 'log': str(directory / 'check.log')})
        print(f'rejected TLA+ mutant: {name}', flush=True)

    name = 'projection-kills-faulted-rax'
    directory = work / name
    directory.mkdir()
    for path in (ROOT / 'Specs').glob('*.tla'):
        shutil.copy2(path, directory / path.name)
    shutil.copy2(ROOT / 'Specs/AMD64RegisterCoreProjection.cfg', directory)
    projection_source = TLA_PROJECTION.read_text()
    (directory / TLA_PROJECTION.name).write_text(replace_once(
        projection_source,
        '~Effects!Sound(Locations, {NormalWrite, RollbackFault},',
        'Effects!Sound(Locations, {NormalWrite, RollbackFault},', name))
    command = [os.environ.get('TLC', 'tlc'), '-workers', '1',
               '-metadir', str(directory / 'states'), '-config',
               'AMD64RegisterCoreProjection.cfg', TLA_PROJECTION.name]
    code, output = run(command, directory, directory / 'check.log')
    if code == 0 or 'Invariant Safety is violated' not in output:
        raise ValueError(f'{name}: intended TLC safety rejection absent; {directory / "check.log"}')
    results.append({'name': name, 'kind': 'tlc-invariant',
                    'command': command, 'log': str(directory / 'check.log')})
    print(f'rejected TLA+ mutant: {name}', flush=True)

    name = 'fault-commits-register'
    directory = work / name
    directory.mkdir()
    for path in (ROOT / 'Specs').glob('*.tla'):
        shutil.copy2(path, directory / path.name)
    shutil.copy2(ROOT / 'Specs/AMD64RegisterCoreFault.cfg', directory)
    (directory / TLA_FAULT.name).write_text(replace_once(
        TLA_FAULT.read_text(), 'LockFault.committed = 0',
        'LockFault.committed = 1', name))
    command = [os.environ.get('TLC', 'tlc'), '-workers', '1',
               '-metadir', str(directory / 'states'), '-config',
               'AMD64RegisterCoreFault.cfg', TLA_FAULT.name]
    code, output = run(command, directory, directory / 'check.log')
    if code == 0 or 'Invariant Safety is violated' not in output:
        raise ValueError(f'{name}: intended TLC safety rejection absent; {directory / "check.log"}')
    results.append({'name': name, 'kind': 'tlc-invariant',
                    'command': command, 'log': str(directory / 'check.log')})
    print(f'rejected TLA+ mutant: {name}', flush=True)

    version = subprocess.run(['lake', '--version'], cwd=ROOT / 'lean',
                             capture_output=True, text=True, timeout=30)
    if version.returncode or 'Lean version 4.33.1' not in version.stdout:
        raise ValueError('exact Lean 4.33.1 toolchain unavailable')
    lean_source = LEAN.read_text()
    lean_mutations = [
        ('lean-forgets-sign',
         'immediateBitsRef (lowOnes 32) 32 64 .sign',
         'immediateBitsRef (lowOnes 32) 32 64 .zero'),
        ('lean-missing-rex-w',
         '(gprOperand 0 .full64 .write 1) (immediateOperand 1 32 64 .sign) [.rexW]',
         '(gprOperand 0 .full64 .write 1) (immediateOperand 1 32 64 .sign) []'),
    ]
    for name, old, new in lean_mutations:
        path = work / f'{name}.lean'
        path.write_text(replace_once(lean_source, old, new, name))
        command = ['lake', 'env', 'lean', str(path)]
        code, output = run(command, ROOT / 'lean', work / f'{name}.log')
        if code == 0 or not any(marker in output for marker in
                                ('unsolved goals', 'tactic \'decide\' failed',
                                 'Tactic `decide` proved that the proposition',
                                 'is not definitionally equal')):
            raise ValueError(f'{name}: intended Lean proof failure absent; {work / (name + ".log")}')
        results.append({'name': name, 'kind': 'lean-proof',
                        'command': command, 'log': str(work / f'{name}.log')})
        print(f'rejected Lean mutant: {name}', flush=True)

    name = 'lean-projection-kills-faulted-rax'
    path = work / f'{name}.lean'
    path.write_text(replace_once(
        LEAN_PROJECTION.read_text(),
        'sound [normalWrite, rollbackFault] [] raxCells raxCells = false',
        'sound [normalWrite, rollbackFault] [] raxCells raxCells = true', name))
    command = ['lake', 'env', 'lean', str(path)]
    code, output = run(command, ROOT / 'lean', work / f'{name}.log')
    if code == 0 or 'Tactic `decide` proved that the proposition' not in output:
        raise ValueError(f'{name}: intended Lean proof rejection absent; {work / (name + ".log")}')
    results.append({'name': name, 'kind': 'lean-proof',
                    'command': command, 'log': str(work / f'{name}.log')})
    print(f'rejected Lean mutant: {name}', flush=True)

    name = 'lean-fault-commits-register'
    path = work / f'{name}.lean'
    path.write_text(replace_once(
        lean_source, 'mov64LockFault.committedEffects = [] := by',
        'mov64LockFault.committedEffects = ["gpr:rax"] := by', name))
    command = ['lake', 'env', 'lean', str(path)]
    code, output = run(command, ROOT / 'lean', work / f'{name}.log')
    if code == 0 or not any(marker in output for marker in
                            ('unsolved goals', 'simp made no progress',
                             'does not match the goal', 'is not definitionally equal')):
        raise ValueError(f'{name}: intended Lean proof rejection absent; {work / (name + ".log")}')
    results.append({'name': name, 'kind': 'lean-proof',
                    'command': command, 'log': str(work / f'{name}.log')})
    print(f'rejected Lean mutant: {name}', flush=True)

    stable = source_hashes == {name: digest(ROOT / name) for name in source_hashes}
    report = {'recordedUtc': datetime.now(timezone.utc).isoformat(),
              'sourceSha256': source_hashes, 'sourcesStable': stable,
              'leanVersion': version.stdout.strip(), 'mutations': results,
              'passed': stable and len(results) == 9}
    (work / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Report: {work / "report.json"}', flush=True)
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
