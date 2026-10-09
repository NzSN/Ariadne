#!/usr/bin/env python3
"""Independent controlled producer / opaque CPUID / consumer fixture."""
import argparse,hashlib,json
from pathlib import Path
import make_stage_b as base
HERE=Path(__file__).resolve().parent
CASES=[('opaque', '4889d9 0fa2 c70105000000 c3',5),
       ('observed','4883ec58 0fb64038 4831e0 80783876 c3',11),
       ('empty','4889d9 f8 c70105000000 c3',4)]
def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();out=HERE/'admission';out.mkdir(exist_ok=True);rows=[]
 for label,code,seed_offset in CASES:
  base.CODE=bytes.fromhex(code)
  for platform,target,entry in [(2,'windows',0x7ff700001000),(0x8201,'linux',0x401000)]:
   raw=base.build(platform,entry);dest=out/(label+'-'+target+'.dmp')
   if a.check:
    if dest.read_bytes()!=raw:raise SystemExit('controlled admission fixture differs: '+str(dest))
   else:dest.write_bytes(raw)
   rows.append(dict(name=dest.name,entry=f'0x{entry:016x}',seed=f'0x{entry+seed_offset:016x}',sha256=hashlib.sha256(raw).hexdigest(),kind=label,expectedDecoded=5 if label=='observed' else 4 if label=='opaque' else 1))
 text=json.dumps(dict(schema='ariadne.admission-controlled-fixtures/v1',captureKind='synthetic tool-produced minidump; not external Electron capture',rows=rows),indent=2)+'\n';dest=out/'manifest.json'
 if a.check:
  if dest.read_text()!=text:raise SystemExit('controlled admission fixture manifest differs')
 else:dest.write_text(text)
 print('Six independent admission minidumps match' if a.check else 'Generated six independent admission minidumps')
if __name__=='__main__':main()
