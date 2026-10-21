#!/usr/bin/env python3
"""Independent byte/integer oracle; never imports the production resolver."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def targets(base, words, lower, upper, missing=()):
    result = set()
    for index in range(lower, upper + 1):
        if index in missing:
            continue
        raw = bytes.fromhex(words[index])
        assert len(raw) == 4
        value = sum(byte * (256 ** position) for position, byte in enumerate(raw))
        signed = value if value < 2 ** 31 else value - 2 ** 32
        result.add((base + signed) % (2 ** 64))
    return sorted(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    fixture = ROOT / 'tests/bap/fixtures/target-resolution-oracle.json'
    cases = json.loads(fixture.read_text())['cases']
    for case in cases:
        actual = targets(int(case['base'], 16), case['words'], case['lower'],
                         case['upper'], case['missing'])
        assert [f'0x{value:016x}' for value in actual] == case['expected'], case['name']
    table = ROOT / 'tests/bap/fixtures/target-resolution-table.bin'
    record = json.loads(table.with_name('jump-table-inspection.json').read_text())
    data = table.read_bytes()
    actual = targets(int(record['table_base'], 16),
                     [data[offset:offset+4].hex() for offset in range(0, len(data), 4)], 0, 57)
    assert [f'0x{value:016x}' for value in actual] == record['unique_targets']
    result = {'schema': 'ariadne.target-resolution-oracle/v1', 'cases': len(cases),
              'actual_capture_entries': 58, 'actual_capture_targets': len(actual),
              'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
              'table_sha256': hashlib.sha256(data).hexdigest()}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
