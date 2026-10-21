#!/usr/bin/env python3
"""Independent finite sequence/domain equivalence; no formal checker or SUT."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]


def recurrence(n,tag):
    if n==0:
        return []
    previous=recurrence(n-1,tag)
    previous.append(tag)
    return previous


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    model=ROOT/'Specs/AriadneAddressWrap.tla'
    text=model.read_text()
    definition=next(line for line in text.splitlines()if line.startswith('Repeat(n,tag) =='))
    assert re.sub(r'\s+','',definition)=='Repeat(n,tag)==IFn=0THEN<<>>ELSEAppend(Repeat(n-1,tag),tag)', 'changed recurrence/cap'
    assert re.search(r'RECURSIVE\s+Repeat\(_,\s*_\)',text)
    lengths=list(range(43))+[64]
    count=0
    for length in lengths:
        for tag in ['field','control']:
            actual=recurrence(length,tag)
            independent={index:tag for index in range(1,length+1)}
            assert len(actual)==length
            assert {index+1:value for index,value in enumerate(actual)}==independent
            count+=1
    result={'schema':'ariadne.i5c-w0-repeat-equivalence/v1','passed':True,
            'lengths':lengths,'tags':['field','control'],'cases':count,
            'source_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
            'no_hidden_cap':len(recurrence(64,'control'))==64,
            'method':'source-form check plus independent recurrence/domain-map equality; TLC also checks RepeatContract',
            'apalache_bounded_smt_claimed':False}
    payload=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_text(payload)
    print(payload,end='')


if __name__=='__main__':main()
