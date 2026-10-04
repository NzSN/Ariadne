#!/usr/bin/env python3
"""Independent finite Windows exception-context fixtures for I5a (not real captures)."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent / 'i5a'
SITE = 0x401000
MASK = (1 << 64) - 1
REGISTERS = {'rax':120,'rcx':128,'rdx':136,'rbx':144,'rsp':152,'rbp':160,'rsi':168,'rdi':176,
             'r8':184,'r9':192,'r10':200,'r11':208,'r12':216,'r13':224,'r14':232,'r15':240,'rip':248}

def case(name, code='c70005000000', registers=None, terms=None, constant=0, width=32, operation=1, **overrides):
    registers = registers or {'rax':0}
    terms = terms if terms is not None else {'rax':1}
    address = (constant + sum(registers.get(r, 0)*n for r,n in terms.items())) & MASK
    row = dict(name=name, code=code, registers=registers, terms=terms, constant=constant & MASK,
               access_width=width, operation=operation, address=address, flags=0x100003,
               platform=2, exception_code=0xc0000005, exception_flags=0, chain=0,
               exception_location=SITE, rip=SITE, parameters=[operation,address],
               outcome='consistent_with_evidence' if address==0 else 'refuted_under_premises')
    row.update(overrides)
    return row

CASES = [
    case('zero-store'), case('nonzero-store',registers={'rax':0x1000}),
    case('null-base-offset',code='c7400805000000',constant=8),
    case('indexed-wrap',code='48c70408ffffffff',registers={'rax':MASK,'rcx':1},terms={'rax':1,'rcx':1},width=64),
    case('load32-zero',code='8b03',registers={'rbx':0},terms={'rbx':1},operation=0),
    case('load64-indexed',code='488b448b08',registers={'rbx':0x1000,'rcx':2},terms={'rbx':1,'rcx':4},constant=8,width=64,operation=0),
    case('store32-negative',code='8985b8feffff',registers={'rbp':0x148,'rax':123},terms={'rbp':1},constant=-0x148),
    case('store64-zero',code='488903',registers={'rbx':0,'rax':123},terms={'rbx':1},width=64),
    case('rip-load',code='488b0508000000',terms={},registers={'rax':123},constant=SITE+7+8,width=64,operation=0),
    case('rip-zero',code='488b05f9efbfff',terms={},registers={'rax':123},constant=0,width=64,operation=0),
    case('rsp-control-only',code='c7042405000000',registers={'rsp':0},terms={'rsp':1},flags=0x100001),
    case('rip-control-only',code='488b0508000000',terms={},constant=SITE+15,width=64,operation=0,flags=0x100001),
    case('last-access-byte',parameters=[1,3]),
    case('past-access-span',parameters=[1,4],outcome='unknown'),
    case('low-range-edge',registers={'rax':0x800000000000-4}),
    case('cross-low-range',registers={'rax':0x800000000000-3},outcome='unknown'),
    case('wrong-context-architecture',flags=0x200003,outcome='unknown'),
    case('missing-integer',flags=0x100001,outcome='unknown'),
    case('missing-control',flags=0x100002,outcome='unknown'),
    case('no-parameters',parameters=[],outcome='unknown'),
    case('one-parameter',parameters=[1],outcome='unknown'),
    case('wrong-kind',exception_code=0x80000003,outcome='unknown'),
    case('execute',parameters=[8,0],outcome='unknown'),
    case('nested',chain=0x1234,outcome='unknown'),
    case('unknown-flags',exception_flags=0x100,outcome='unknown'),
    case('wrong-pc',exception_location=SITE+1,outcome='unknown'),
    case('wrong-rip',rip=SITE+1,outcome='unknown'),
    case('wrong-operation',parameters=[0,0],outcome='unknown'),
    case('wrong-data-address',parameters=[1,0x1000],outcome='unknown'),
    case('linux',platform=0x8201,outcome='unknown'),
    case('segment',code='64c70005000000',outcome='unknown'),
    case('address-size',code='67c70005000000',outcome='unknown'),
    case('repeat',code='f3c70005000000',outcome='unknown'),
    case('lock',code='f0c70005000000',outcome='unknown'),
    case('stack',code='50',outcome='unknown'),
    case('excluded-range',registers={'rax':0x800000000000},outcome='unknown'),
    case('span-wrap',registers={'rax':MASK},outcome='unknown'),
    case('no-context',context_absent=True,outcome='unknown'),
    case('no-exception',exception_absent=True,outcome='unknown'),
    case('thread-fallback',flags=0x100001,thread_list_context=True,outcome='unknown'),
    case('noncontinuable',exception_flags=1),
]

def build(row):
    data=bytearray(32);streams=[]
    def append(payload):
        offset=len(data);data.extend(payload);return offset
    def stream(kind,payload):
        offset=append(payload);streams.append((kind,len(payload),offset));return offset
    system=bytearray(56);system[0]=9;system[6]=1;struct.pack_into('<I',system,20,row['platform']);stream(7,system)
    code=bytes.fromhex(row['code'])+b'\xc3';code_offset=append(code)
    stream(5,struct.pack('<IQII',1,SITE,len(code),code_offset))
    context=bytearray(1232);struct.pack_into('<I',context,48,row['flags'])
    for name,value in row['registers'].items():struct.pack_into('<Q',context,REGISTERS[name],value)
    struct.pack_into('<Q',context,248,row['rip'])
    context_offset=append(context)
    if row.get('thread_list_context'):
        other=bytearray(context);struct.pack_into('<I',other,48,0x100003)
        other_offset=append(other);thread=bytearray(48);struct.pack_into('<I',thread,0,17)
        struct.pack_into('<II',thread,40,len(other),other_offset);stream(3,struct.pack('<I',1)+thread)
    exception=bytearray(168);struct.pack_into('<I',exception,0,17)
    struct.pack_into('<IIQQI',exception,8,row['exception_code'],row['exception_flags'],row['chain'],row['exception_location'],len(row['parameters']))
    for i,value in enumerate(row['parameters']):struct.pack_into('<Q',exception,40+i*8,value)
    struct.pack_into('<II',exception,160,0 if row.get('context_absent') else len(context),context_offset)
    exception_offset=None if row.get('exception_absent') else stream(6,exception)
    directory=len(data);struct.pack_into('<4sIII',data,0,b'MDMP',0xA793,len(streams),directory)
    for item in streams:data.extend(struct.pack('<III',*item))
    return bytes(data),dict(code_offset=code_offset,context_offset=context_offset,exception_offset=exception_offset)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    HERE.mkdir(exist_ok=True);rows=[]
    for row in CASES:
        payload,offsets=build(row);path=HERE/(row['name']+'.dmp')
        if args.check:assert path.read_bytes()==payload,path
        else:path.write_bytes(payload)
        rows.append(dict(row,site=SITE,sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload),offsets=offsets))
    manifest=json.dumps({'schema':'ariadne.i5a-fixtures/v1','scope':'Independent synthetic exception-context fixtures; no real Windows qualification','cases':rows},indent=2,sort_keys=True)+'\n'
    path=HERE/'manifest.json'
    if args.check:assert path.read_text()==manifest,path
    else:path.write_text(manifest)
    print('I5a fixtures:',len(rows),'independent cases checked' if args.check else 'generated')
if __name__=='__main__':main()
