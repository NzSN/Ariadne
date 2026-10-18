#!/usr/bin/env python3
"""Independent finite oracle: Floyd-Warshall closure and path permutations.

No Ariadne executable or output is consumed to produce these expectations.
"""
import argparse
import itertools
import json
from pathlib import Path


def expected(n, edges):
    r = [[i == j for j in range(n)] for i in range(n)]
    for a, b, _ in edges:
        r[a][b] = True
    for k in range(n):
        for i in range(n):
            for j in range(n):
                r[i][j] |= r[i][k] and r[k][j]
    groups = sorted({tuple(j for j in range(n) if r[i][j] and r[j][i]) for i in range(n)})
    lengths = []
    if n == 1:
        lengths = [0]
    else:
        for k in range(n - 1):
            for middle in itertools.permutations(range(1, n - 1), k):
                p = (0,) + middle + (n - 1,)
                if all(any(a == x and b == y for a, b, _ in edges) for x, y in zip(p, p[1:])):
                    lengths.append(len(p) - 1)
    return dict(n=n, edges=edges, forward=[j for j in range(n) if r[0][j]],
                backward=[i for i in range(n) if r[i][n-1]],
                corridor=[i for i in range(n) if r[0][i] and r[i][n-1]],
                groups=groups, cyclic=[len(g)>1 or any(a==b==g[0] for a,b,_ in edges) for g in groups],
                shortest=min(lengths) if lengths else None)


def corpus():
    cases = [expected(3, [[i, j, 'next'] for i in range(3) for j in range(3) if mask & (1 << (3*i+j))]) for mask in range(512)]
    cases += [expected(4, [[0,1,'taken'],[0,2,'fallthrough'],[1,3,'next'],[2,3,'next']]),
              expected(3, [[0,1,'taken'],[0,1,'fallthrough'],[1,2,'next']]),
              expected(1, [[0,0,'jump']]), expected(1, [])]
    return cases


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    path=Path(__file__).with_suffix('.json')
    encoded=json.dumps(corpus(),sort_keys=True,separators=(',',':'))+'\n'
    if args.check:
        assert path.read_text()==encoded, 'literal oracle fixture changed'
        print(f'{len(corpus())} independent closure/SCC/shortest expectations passed')
    else:
        path.write_text(encoded)

if __name__=='__main__': main()
