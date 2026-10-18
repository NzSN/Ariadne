#!/usr/bin/env python3
"""Literal finite expectations from concrete enumeration, not Ariadne output."""
import argparse,json,itertools
from pathlib import Path

def corpus():
    masks=[]
    for mask in range(16):
        for bits in range(16):
            if bits & ~mask:continue
            values=[n for n in range(16) if n&mask==bits]
            for constant in range(16):
                masks.append(dict(mask=mask,bits=bits,constant=constant,
                    permitted=values,and_values=sorted({v&constant for v in values}),
                    add_values=sorted({(v+constant)%16 for v in values})))
    inverses=[]
    for op in ['copy','add','sub','and','constant']:
        for constant in range(16):
            for endpoint in range(16):
                f=lambda n: n if op=='copy' else (n+constant)%16 if op=='add' else (n-constant)%16 if op=='sub' else n&constant if op=='and' else constant
                inverses.append(dict(op=op,constant=constant,endpoint=endpoint,
                    inputs=[n for n in range(16) if f(n)==endpoint]))
    # Independent round allocation: two question slots, then one each other band.
    # The runtime queue uses cyclic slots (question, relevant, question, coverage).
    schedule=[0,2,1,3,0,2,1,3,0,2,1,3]
    return dict(schema='ariadne.frame-question-oracle/v1',masks=masks,inverses=inverses,
                scheduler=dict(bands=[[0,1],[2],[3]],first_twelve=schedule),
                writer_universe=['entry','instruction','opaque','external'],
                verdicts=[dict(allowed=[2,4],predicate=0,closed=True,witness=False,result='refuted_under_model'),dict(allowed=[0,2],predicate=0,closed=True,witness=True,result='possible_under_model'),dict(allowed=[0,2],predicate=0,closed=True,witness=False,result='unknown'),dict(allowed=[2,4],predicate=0,closed=False,witness=False,result='unknown'),dict(allowed=[],predicate=0,closed=True,witness=False,result='premise_conflict')])

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    path=Path(__file__).with_suffix('.json');text=json.dumps(corpus(),sort_keys=True,separators=(',',':'))+'\n'
    if a.check:assert path.read_text()==text;print(f'{len(corpus()["masks"])} bit-domain and {len(corpus()["inverses"])} inverse expectations pass')
    else:path.write_text(text)
if __name__=='__main__':main()
