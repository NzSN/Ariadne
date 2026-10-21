#!/usr/bin/env python3
"""Independent Python integer evaluation of projected model inputs, not TLC."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE_DIR=ROOT/"tests/input/fixtures/i5c"
MODULUS=18446744073709551616
CUTOFF=140737488355328


def integer(limbs):
    assert len(limbs) in (2,4) and all(type(n)is int and 0<=n<65536 for n in limbs)
    return sum(number*(65536**index) for index,number in enumerate(limbs))


def result(c):
    if not c['bindingValid']:
        return dict(expectedConclusion='error',expectedFacts=False,expectedQuotient=0,
                    expectedEffective=[0]*4,expectedTruncated=False,expectedEvidence=0,expectedClaims=0)
    base=integer(c['base'])
    encoded=integer(c['displacement'])
    disp=encoded-4294967296 if encoded>=2147483648 else encoded
    total=base+disp
    # Distinct direct comparisons/subtraction, not oracle.expected()/divmod().
    quotient=-1 if total<0 else 1 if total>=MODULUS else 0
    ea=total-quotient*MODULUS
    # Independently check the model's actual four-limb carry construction.
    carry=0
    model_effective=[]
    extension=[c['displacement'][0],c['displacement'][1]]+([65535]*2 if disp<0 else [0]*2)
    for left,right in zip(c['base'],extension):
        number=left+right+carry
        carry=number//65536
        model_effective.append(number%65536)
    assert integer(model_effective)==ea
    assert carry-int(disp<0)==quotient
    control=bool(c['contextFlags']&1)
    integer_valid=bool(c['contextFlags']&2)
    supported={'MOV32mi':(4,1),'MOV64mi32':(8,1),'MOV32rm':(4,0),
               'MOV64rm':(8,0),'MOV32mr':(4,1),'MOV64mr':(8,1)}
    ready=all(c[key] for key in ('windows','exception','context','contextSupported','ordinaryAV',
                                'siteMatches','captured','reached','semantics','prefix','oneAccess',
                                'receipt','receiptMatches','baseOnly'))
    ready=ready and control and c['parameters']>=2
    ready=ready and (control if c['baseGroup']==1 else integer_valid)
    ready=ready and supported.get(c['form'])==(c['accessBytes'],c['operation'])
    ready=ready and integer(c['bapAddress'])==ea
    register_count=(3*int(control)+15*int(integer_valid)) if c['contextSupported'] else 0
    atoms=['instruction']
    if c['exception']:
        atoms.append('record')
        if c['context']:
            atoms.append('context')
        atoms.extend(['field']*(8+c['parameters']+(1+register_count if c['context'] else 0)))
    if c['receipt']:
        atoms.append('receipt')
    retained=atoms[:c['evidenceLimit']]
    observed=sum(tag=='field' or tag=='instruction' and c['captured'] for tag in retained)
    fits=len(atoms)<=c['evidenceLimit']
    needed=observed+5*int(ready and fits)+1
    claims_fit=needed<=c['claimLimit']
    keep=ready and fits and claims_fit
    end=ea+c['accessBytes']
    eligible=keep and end<MODULUS and end<=CUTOFF and ea<=integer(c['reported'])<end
    conclusion=('consistent_with_evidence' if quotient else 'refuted_under_premises') if eligible else 'unknown'
    claims=needed if claims_fit else min(observed,c['claimLimit'])+int(c['claimLimit']>observed)
    return dict(expectedConclusion=conclusion,expectedFacts=keep,
                expectedQuotient=quotient if keep else 0,
                expectedEffective=model_effective if keep else [0]*4,
                expectedTruncated=not fits or not claims_fit,
                expectedEvidence=len(retained),expectedClaims=claims)


def check():
    paths={name:FIXTURE_DIR/name for name in ('manifest.json','model-cases.json')}
    fixture=json.loads(paths['manifest.json'].read_text())
    model=json.loads(paths['model-cases.json'].read_text())
    assert model['independent_fixture_sha256']==hashlib.sha256(paths['manifest.json'].read_bytes()).hexdigest()
    cases={row['name']:row for row in fixture['cases']}
    assert len(model['cases'])==52 and len({row['name'] for row in model['cases']})==52
    for row in model['cases']:
        for key,value in result(row).items():
            assert row[key]==value,(row['name'],key,row[key],value)
        if row['name'] in cases:
            payload=cases[row['name']]['payload']
            assert len(row['payload'])==4
            assert integer(row['payload'])==(0 if payload is None else payload)
            oracle=cases[row['name']]['expected']
            assert row['expectedConclusion']==oracle['conclusion']
            assert row['expectedFacts']==(oracle['arithmetic']is not None)
            assert row['expectedEvidence']==oracle['retained_evidence_count']
            assert row['expectedClaims']==oracle['retained_claims']
    assert model['configurations']=={'AddressWrap':52,'AddressWrapArithmetic':23,
        'AddressWrapAdmission':12,'AddressWrapBudgets':11,'AddressWrapForms':6,'AddressWrapPayload':2}
    # TLA case fields declared Int must never contain Python None spellings.
    text=(ROOT/'Specs/AriadneAddressWrapCases.tla').read_text()
    assert '|-> None' not in text,'unrepresentable Python None in generated TLA input'
    return dict(schema='ariadne.i5c-w0-input-crosscheck/v1',passed=True,records=52,
                configurations=model['configurations'],payload_values_checked=50,
                model_executed=False,sut_executed=False,
                scope='Independent integer/limb/readiness/budget evaluation of projected inputs only; not formal model execution',
                sources={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=check()
    if args.output:
        args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True))
