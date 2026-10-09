"""Independent scalar AMD64 expectations, frozen before projection changes."""
import json
from pathlib import Path
FLAGS=['flag:'+f for f in ('af','cf','of','pf','sf','zf')]
def cells(bank,n=8):return [f'gpr:{bank}:{i}' for i in range(n)]
def expected(uses=(),may=(),must=(),**rest):
 return dict(uses=sorted(set(uses)),may_defs=sorted(set(may)),must_defs=sorted(set(must)),**rest)
CATALOGUE=sorted([*sum((cells(b) for b in ['rax','rcx','rdx','rbx','rsp','rbp','rsi','rdi',*[f'r{i}' for i in range(8,16)]]),[]),*FLAGS,'flag:df','memory:any','state:other'])
CASES=[
 ('sub-rsp-observed','4883ec58',expected(cells('rsp'),cells('rsp')+FLAGS,cells('rsp')+FLAGS)),
 ('sub-rax-zero','4883e800',expected(cells('rax'),cells('rax')+FLAGS,cells('rax')+FLAGS)),
 ('sub-rax-positive-limit','4883e87f',expected(cells('rax'),cells('rax')+FLAGS,cells('rax')+FLAGS)),
 ('sub-rax-negative-limit','4883e880',expected(cells('rax'),cells('rax')+FLAGS,cells('rax')+FLAGS)),
 ('sub-rax-negative-one','4883e8ff',expected(cells('rax'),cells('rax')+FLAGS,cells('rax')+FLAGS)),
 ('movzx-eax-observed','0fb64038',expected(cells('rax')+['memory:any'],cells('rax'),cells('rax'),access={'role':'load','width':8,'base':'rax','index':None,'scale':1,'displacement':56})),
 ('movzx-r14d-observed','440fb67038',expected(cells('rax')+['memory:any'],cells('r14'),cells('r14'),access={'role':'load','width':8,'base':'rax','index':None,'scale':1,'displacement':56})),
 ('movzx-index-negative','0fb6448bf8',expected(cells('rbx')+cells('rcx')+['memory:any'],cells('rax'),cells('rax'),access={'role':'load','width':8,'base':'rbx','index':'rcx','scale':4,'displacement':-8})),
 ('xor-distinct-observed','4831e0',expected(CATALOGUE,cells('rax')+FLAGS,cells('rax')+[f for f in FLAGS if f!='flag:af'],undefined_flags=['flag:af'])),
 ('xor-self','4831c0',expected(CATALOGUE,cells('rax')+FLAGS,cells('rax')+[f for f in FLAGS if f!='flag:af'],undefined_flags=['flag:af'])),
 ('cmp-byte-observed','80783876',expected(cells('rax')+['memory:any'],FLAGS,FLAGS,access={'role':'load','width':8,'base':'rax','index':None,'scale':1,'displacement':56})),
 ('cmp-byte-zero','803800',expected(cells('rax')+['memory:any'],FLAGS,FLAGS,access={'role':'load','width':8,'base':'rax','index':None,'scale':1,'displacement':0})),
 ('cmp-byte-negative','8078f8ff',expected(cells('rax')+['memory:any'],FLAGS,FLAGS,access={'role':'load','width':8,'base':'rax','index':None,'scale':1,'displacement':-8})),
 # Same BIL/control capabilities, different actual encodings (P2).
 ('add-immediate','4883c008',expected(cells('rax'),cells('rax')+FLAGS,cells('rax')+FLAGS)),
 ('jne-long','0f8502000000',expected(['flag:zf'])),
 ('jmp-long','e902000000',expected()),
 ('clc-capability','f8',expected((),['flag:cf'],['flag:cf'])),
]
def arithmetic(op,a,b,width):
 mask=(1<<width)-1;a&=mask;b&=mask
 result=(a-b if op in ('sub','cmp') else a^b)&mask
 flags=dict(cf=int(a<b) if op in ('sub','cmp') else 0,
            of=int(bool((a^b)&(a^result)&(1<<(width-1)))) if op in ('sub','cmp') else 0,
            af=int(bool((a^b^result)&16)) if op in ('sub','cmp') else None,
            pf=int((result&255).bit_count()%2==0),sf=(result>>(width-1))&1,zf=int(result==0))
 return dict(result=result,flags=flags)
def contract():
 numeric=[]
 for op,width in [('sub',64),('cmp',8),('xor',64)]:
  for a,b in [(0,0),(0,1),(1,1),((1<<(width-1))-1,-1),(1<<(width-1),1),((1<<width)-1,0),((1<<width)-1,127),(0,-128)]:
   numeric.append(dict(op=op,width=width,a=a,b=b,expected=arithmetic(op,a,b,width)))
 return dict(schema='ariadne.bap-admission-contract/v1',projection='bap-bit-provenance-v3',
  numericOracle='Python unbounded integers, explicit modulo and independent scalar flag equations',cases=[dict(name=n,bytes=h,expected=e) for n,h,e in CASES],numericCases=numeric,
  decisions={'supported_typed_bil':'projected','ordinary_unsupported_data':'opaque-ordinary with all uses/may-defs and no must-defs',
   'empty_except_exact_90':'opaque-unsupported stop','unknown_control_or_namespace':'opaque-unsupported stop',
   'guarded_prefix':'opaque-unsupported stop','malformed_type_or_operand_binding':'fail or explicit disagreement stop; never continuation','budget':'query error'},
  exclusions=['LOCK','REP','FS/GS','address-size override','SIMD/x87/system state','BIL While/Special/Exception','invented indirect targets'],
  premises=['normal continuation only','captured bytes and independent control match','unknown AF retains old origins','memory:any never must-killed','source and payload excluded from address inputs'])
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 dest=Path(__file__).with_name('contract.json');text=json.dumps(contract(),indent=2)+'\n'
 if a.check:
  if dest.read_text()!=text:raise SystemExit('independent admission contract differs')
 else:dest.write_text(text)
 print('Independent admission contract:',len(CASES),'encodings and',len(contract()['numericCases']),'numeric cases')
