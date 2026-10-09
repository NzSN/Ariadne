#!/usr/bin/env python3
"""Compare pinned typed BIL with independent frozen scalar integer equations."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests/bap/fixtures/admission'))
from oracle import arithmetic
class Value:
 def __init__(self,n,w):self.n=None if n is None else n&((1<<w)-1);self.w=w
 def signed(self):return self.n-(1<<self.w) if self.n&(1<<(self.w-1)) else self.n
class Evaluator:
 def __init__(self,registers,memory):self.values=registers.copy();self.memory=memory
 def expr(self,e):
  k=e['kind']
  if k=='var':return self.memory if e['var']['type']=='mem' else self.values[e['var']['name']]
  if k=='int':
   n,w=e['value'].split(':');return Value(int(n,0),int(w.rstrip('us')))
  if k=='unknown':return Value(None,1)
  if k=='load':
   a=self.expr(e['addr']).n;return Value(sum(self.memory[(a+i)&((1<<64)-1)]<<(8*i) for i in range(e['width']//8)),e['width'])
  if k=='cast':
   v=self.expr(e['arg']);w=e['width'];op=e['op']
   if v.n is None:return Value(None,w)
   return Value(v.signed() if op==2 else v.n>>(v.w-w) if op==1 else v.n,w)
  if k=='extract':
   v=self.expr(e['arg']);return Value(None if v.n is None else v.n>>e['lo'],e['hi']-e['lo']+1)
  if k=='concat':
   l=self.expr(e['lhs']);r=self.expr(e['rhs']);return Value(None if l.n is None or r.n is None else l.n<<r.w|r.n,l.w+r.w)
  if k=='unop':
   v=self.expr(e['arg']);return Value(None if v.n is None else ~v.n if e['op']==0 else -v.n,v.w)
  if k=='binop':
   l=self.expr(e['lhs']);r=self.expr(e['rhs']);op=e['op'];w=1 if op<=5 else l.w
   if l.n is None or r.n is None:return Value(None,w)
   a,b=l.n,r.n
   signed_q=lambda:(abs(l.signed())//abs(r.signed()))*(-1 if (l.signed()<0)!=(r.signed()<0) else 1)
   # Actual pinned bap.h enum: comparisons descend from SLE to EQ;
   # arithmetic descends from SMOD to PLUS. This is not LLVM's enum.
   actions={0:lambda:l.signed()<=r.signed(),1:lambda:l.signed()<r.signed(),2:lambda:a<=b,3:lambda:a<b,4:lambda:a!=b,5:lambda:a==b,
    6:lambda:a^b,7:lambda:a|b,8:lambda:a&b,9:lambda:l.signed()>>b,10:lambda:a>>b,11:lambda:a<<b,12:lambda:l.signed()-signed_q()*r.signed(),13:lambda:a%b,14:signed_q,15:lambda:a//b,16:lambda:a*b,17:lambda:a-b,18:lambda:a+b}
   if op not in actions:raise ValueError('oracle unsupported actual BIL operator '+str(op))
   return Value(int(actions[op]()),w)
  if k=='ite':
   c=self.expr(e['condition']);assert c.n is not None;return self.expr(e['yes'] if c.n else e['no'])
  if k=='let':
   name=e['var']['name'];old=self.values.get(name);self.values[name]=self.expr(e['value']);result=self.expr(e['body'])
   if old is None:del self.values[name]
   else:self.values[name]=old
   return result
  raise ValueError('oracle unsupported actual BIL expression '+k)
 def statements(self,statements):
  for s in statements:
   if s['kind']=='move':self.values[s['var']['name']]=self.expr(s['value'])
   elif s['kind']=='if':
    c=self.expr(s['condition']);assert c.n is not None;self.statements(s['yes'] if c.n else s['no'])
   else:raise ValueError('oracle unexpected actual BIL statement '+s['kind'])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 contract_path=ROOT/'tests/bap/fixtures/admission/contract.json';contract=json.loads(contract_path.read_text());native_path=ROOT/'evidence/Ariadne/bap-admission/p0-native-bil.json';native=json.loads(native_path.read_text())['responses'][1:-1]
 rows=[]
 for case,lift in zip(contract['cases'][:13],native[:13]):
  assert lift['bytes']==case['bytes'] and lift['bil'];name=case['name'];expected=case['expected'];access=expected.get('access')
  for value in [0,1,0x7f,0x80,0xff,(1<<63)-1,1<<63,(1<<64)-1]:
   banks=['RAX','RCX','RDX','RBX','RSP','RBP','RSI','RDI',*[f'R{i}' for i in range(8,16)]]
   registers={bank:Value(0x10000,64) for bank in banks};registers['RCX']=Value(2,64)
   registers.update({f:Value(1,1) for f in ['CF','PF','AF','ZF','SF','OF','DF']})
   memory={}
   if access:
    addr=(registers[access['base'].upper()].n+(registers[access['index'].upper()].n*access['scale'] if access['index'] else 0)+access['displacement'])&((1<<64)-1)
    memory[addr]=value&255
   if name.startswith('sub-'):
    bank='RSP' if name=='sub-rsp-observed' else 'RAX';registers[bank]=Value(value,64)
    immediate=int(case['bytes'][-2:],16);immediate=immediate-256 if immediate>=128 else immediate
    want=arithmetic('sub',value,immediate,64);destination=bank
   elif name.startswith('xor-'):
    registers['RAX']=Value(value,64);registers['RSP']=Value(0xa5a5a5a5a5a5a5a5,64)
    want=arithmetic('xor',value,value if name=='xor-self' else registers['RSP'].n,64);destination='RAX'
   elif name.startswith('cmp-'):
    want=arithmetic('cmp',value,int(case['bytes'][-2:],16),8);destination=None
   else:want={'result':value&255,'flags':{f:1 for f in ['cf','pf','af','zf','sf','of']}};destination='R14' if 'r14d' in name else 'RAX'
   evaluator=Evaluator(registers,memory);evaluator.statements(lift['bil'])
   if destination:assert evaluator.values[destination].n==want['result'],(name,value,'result')
   for flag,result in want['flags'].items():assert evaluator.values[flag.upper()].n==result,(name,value,flag,evaluator.values[flag.upper()].n,result)
   rows.append(dict(case=name,input=value,resultMatches=True,flagsMatch=True))
 a.output.parent.mkdir(parents=True,exist_ok=True)
 sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
 record=dict(schema='ariadne.bap-independent-scalar-oracle/v1',passed=True,comparisons=len(rows),contractSha256=sha(contract_path),typedBilSha256=sha(native_path),oracleSourceSha256=sha(Path(__file__)),rows=rows,scope='Pinned producer arithmetic/flags/zero-extension for thirteen independently specified encodings; no Ariadne provenance evaluator or hardware executor used.')
 a.output.write_text(json.dumps(record,indent=2)+'\n');print('Independent scalar BIL oracle:',len(rows),'comparisons pass')
if __name__=='__main__':main()
