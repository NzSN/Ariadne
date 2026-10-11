#!/usr/bin/env python3
"""Independent Cartesian-product oracle; does not implement SUT graph traversal."""
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def cases():
    possible = [(0, 1), (0, 2), (1, 2), (1, 3), (2, 3), (1, 1)]
    rows = []
    for mask in range(64):
        edges = [edge for i, edge in enumerate(possible) if mask & (1 << i)]
        all_paths = []
        for length in range(2, 7):
            for interior in itertools.product(range(4), repeat=length-2):
                path = (0, *interior, 3)
                if (all(path.count(n) <= 2 for n in range(4)) and
                        all(edge in edges for edge in zip(path, path[1:]))):
                    all_paths.append(list(path))
        rows.append(dict(edges=edges, paths=sorted(all_paths), max_steps=6, max_visits=2))
    return rows


if __name__ == '__main__':
    output = HERE/'frame_paths_oracle.json'
    text = json.dumps(cases(), indent=2)+'\n'
    if output.exists():
        assert output.read_text() == text, 'frozen oracle changed'
    else:
        output.write_text(text)
    print('Independent graph oracle PASS: 64 graphs; exhaustive sequences of length <= 6.')
