#!/usr/bin/env python3
"""Check compact loop regression inputs independently of old run products."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MASK64 = (1 << 64) - 1


def check():
    manifest = json.loads((HERE / 'legacy-manifest.json').read_text())
    assert len(manifest['assets']) == 5
    for asset in manifest['assets']:
        raw = (HERE / asset['asset']).read_bytes()
        assert len(raw) == asset['bytes']
        assert hashlib.sha256(raw).hexdigest() == asset['sha256']
    for name in ('da09', 'dadd'):
        case = json.loads((HERE / ('dump-' + name + '.json')).read_text())
        base = int(case['table_base'], 16)
        targets = set()
        assert len(case['table_entries']) == 10
        for index, entry in enumerate(case['table_entries']):
            assert int(entry['index'], 16) == index
            assert int(entry['slot'], 16) == base + 4 * index
            raw = bytes.fromhex(entry['bytes_hex'])
            assert len(raw) == 4
            target = (base + int.from_bytes(raw, 'little', signed=True)) & MASK64
            assert target == int(entry['target'], 16)
            targets.add(entry['target'])
        assert sorted(targets) == case['expected_targets']
        nodes = set(case['region_sites'])
        assert case['dispatch'] in nodes and case['header'] in nodes
        assert all(edge['src'] in nodes and edge['dst'] in nodes for edge in case['internal_edges'])
    print('Loop fixture source hashes, signed table arithmetic and region edges: PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.parse_args()
    check()
