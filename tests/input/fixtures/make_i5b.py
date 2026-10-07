#!/usr/bin/env python3
"""Independent encodings and integer oracle for finite I5b synthetic captures."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('i5a_builder', HERE / 'make_i5a.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
MASK = (1 << 64) - 1
FORMS = [
    ('MOV32mi', 'c7400805000000', 'c70005000000', 32, 1),
    ('MOV64mi32', '48c7400805000000', '48c70005000000', 64, 1),
    ('MOV32rm', '8b4008', '8b00', 32, 0),
    ('MOV64rm', '488b4008', '488b00', 64, 0),
    ('MOV32mr', '894008', '8900', 32, 1),
    ('MOV64mr', '48894008', '488900', 64, 1),
]


def case(name, code='c7400805000000', base='rax', displacement=8, registers=None,
         width=32, operation=1, terms=None, constant=None, outcome=None, opcode='MOV32mi', **changes):
    registers = registers if registers is not None else {base: 0}
    terms = terms if terms is not None else {base: 1}
    constant = displacement if constant is None else constant
    row = builder.case(name, code, registers, terms, constant, width, operation, **changes)
    row.update(base=base, displacement=displacement, opcode=opcode,
               outcome=outcome or ('consistent_with_evidence' if registers[base] == 0 and displacement != 0
                                  else 'refuted_under_premises'))
    return row


CASES = []
for opcode, offset, zero, width, operation in FORMS:
    label = opcode.lower()
    for suffix, code, reg, displacement in [('positive', offset, 0, 8),
                                             ('nonzero', offset, 0x1000, 8),
                                             ('no-displacement', zero, 0, 0)]:
        CASES.append(case(f'{label}-{suffix}', code, registers={'rax':reg},
                          displacement=displacement, width=width, operation=operation, opcode=opcode))
CASES += [
    case('effective-zero-nonzero-base', registers={'rax':MASK-7}),
    case('disp32-positive', code='c7800801000005000000', displacement=264),
    case('negative-disp8', code='c740f805000000', displacement=-8, registers={'rax':0x1000}),
    case('negative-disp32', code='c780b8feffff05000000', displacement=-328, registers={'rax':0x1000}),
    case('zero-base-negative', code='c740f805000000', displacement=-8, outcome='unknown'),
    case('rsp-sib', code='c744240805000000', base='rsp', flags=0x100001),
    case('rbp-disp8', code='c7450805000000', base='rbp'),
    case('r12-sib', code='41c744240805000000', base='r12'),
    case('r13-disp8', code='41c7450805000000', base='r13'),
    case('indexed', code='c744480805000000', registers={'rax':0,'rcx':0},
         terms={'rax':1,'rcx':2}, outcome='unknown'),
    case('index-only', code='c704050800000005000000', outcome='unknown'),
    case('absolute', code='c704250800000005000000', terms={}, outcome='unknown'),
    case('rip-relative', code='488b0508000000', terms={}, constant=builder.SITE+15,
         width=64, operation=0, opcode='MOV64rm', outcome='unknown'),
    case('merged-base-index', code='c744000805000000', terms={'rax':2}, outcome='unknown'),
    case('payload-zero', code='c7400800000000'),
    case('last-access-byte', parameters=[1,11]),
    case('past-access-span', parameters=[1,12], outcome='unknown'),
    case('missing-integer', flags=0x100001, outcome='unknown'),
    case('missing-control', flags=0x100002, outcome='unknown'),
    case('no-parameters', parameters=[], outcome='unknown'),
    case('one-parameter', parameters=[1], outcome='unknown'),
    case('wrong-kind', exception_code=0x80000003, outcome='unknown'),
    case('execute', parameters=[8,8], outcome='unknown'),
    case('nested', chain=0x1234, outcome='unknown'),
    case('unknown-flags', exception_flags=0x100, outcome='unknown'),
    case('wrong-pc', exception_location=builder.SITE+1, outcome='unknown'),
    case('wrong-rip', rip=builder.SITE+1, outcome='unknown'),
    case('wrong-operation', parameters=[0,8], outcome='unknown'),
    case('wrong-data-address', parameters=[1,0x1000], outcome='unknown'),
    case('linux', platform=0x8201, outcome='unknown'),
    case('segment', code='64c7400805000000', outcome='unknown'),
    case('address-size', code='67c7400805000000', outcome='unknown'),
    case('repeat', code='f3c7400805000000', outcome='unknown'),
    case('lock', code='f0c7400805000000', outcome='unknown'),
    case('excluded-range', registers={'rax':0x800000000000}, outcome='unknown'),
    case('span-wrap', registers={'rax':MASK-8}, outcome='unknown'),
    case('no-context', context_absent=True, outcome='unknown'),
    case('no-exception', exception_absent=True, outcome='unknown'),
    case('thread-fallback', flags=0x100001, thread_list_context=True, outcome='unknown'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    directory = HERE / 'i5b'
    directory.mkdir(exist_ok=True)
    rows = []
    for row in CASES:
        data, offsets = builder.build(row)
        path = directory / (row['name'] + '.dmp')
        if args.check:
            assert path.read_bytes() == data, path
        else:
            path.write_bytes(data)
        rows.append(dict(row, site=builder.SITE, sha256=hashlib.sha256(data).hexdigest(),
                         bytes=len(data), offsets=offsets))
    text = json.dumps(dict(schema='ariadne.i5b-fixtures/v1',
                           scope='Independent synthetic cases; no real Windows acceptance', cases=rows),
                      indent=2, sort_keys=True) + '\n'
    upstream=case('upstream-call',code='e800000000c7400805000000',rip=builder.SITE+5,
                  exception_location=builder.SITE+5)
    payload,_=builder.build(upstream)
    auxiliary=directory/'upstream-call.dmp'
    if args.check: assert auxiliary.read_bytes()==payload
    else: auxiliary.write_bytes(payload)
    manifest = directory / 'manifest.json'
    if args.check:
        assert manifest.read_text() == text
    else:
        manifest.write_text(text)
    print('I5b fixtures:', len(rows), 'checked' if args.check else 'generated')


if __name__ == '__main__':
    main()
