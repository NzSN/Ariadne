#!/usr/bin/env python3
"""Freeze and compare old CLI bytes before/after I5b; no acceptance from history."""
import argparse
import json
from pathlib import Path
import subprocess

from i5a_native_contract import environment, sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    binary = ROOT / 'target/release/ariadne-minidump'
    cases = json.loads((ROOT / 'tests/input/fixtures/i5a/manifest.json').read_text())['cases']
    actual = {}
    for row in cases:
        for backend in ['rust', 'bap']:
            for fmt in ['text', 'json', 'dot']:
                command = [str(binary), str(ROOT / f"tests/input/fixtures/i5a/{row['name']}.dmp"),
                           '--decoder-reference', str(ROOT / 'target/ariadne-llvm-mc'),
                           '--entry', '401000', '--assess-zero-address', '401000',
                           '--memory-access', '0', '--analysis-backend', backend,
                           '--assessment-only', '--format', fmt]
                result = subprocess.run(command, env=environment(), capture_output=True, timeout=60)
                if result.returncode:
                    raise RuntimeError(result.stderr.decode())
                import hashlib
                actual[f"{row['name']}/{backend}/{fmt}"] = hashlib.sha256(result.stdout).hexdigest()
    if args.freeze:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        with args.baseline.open('x') as out:
            json.dump(dict(schema='ariadne.i5b-legacy-baseline/v1', binarySha256=sha(binary),
                           outputs=actual), out, indent=2)
        print('Frozen:', args.baseline, len(actual), 'old assessment outputs', flush=True)
    else:
        expected = json.loads(args.baseline.read_text())['outputs']
        if actual != expected:
            changed = [k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k)]
            raise RuntimeError('old assessment bytes changed: ' + repr(changed))
        print('Legacy I5a bytes PASS:', len(actual), flush=True)


if __name__ == '__main__':
    main()
