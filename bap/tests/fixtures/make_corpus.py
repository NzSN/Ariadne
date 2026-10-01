#!/usr/bin/env python3
"""Retain actual native BIL with independently specified effect expectations."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def cells(bank,n=8):return [f'gpr:{bank}:{i}' for i in range(n)]
def ex(uses=(),may=(),must=(),**kw):return dict(uses=sorted(uses),may_defs=sorted(may),must_defs=sorted(must),**kw)
FLAGS=['flag:'+f for f in ['af','cf','of','pf','sf','zf']]
CASES=[
 ('mov64','4889d8',ex(cells('rbx'),cells('rax'),cells('rax'))),
 ('mov-al','88d8',ex(cells('rbx',1),cells('rax',1),cells('rax',1))),
 ('mov-ah','88dc',ex(cells('rbx',1),['gpr:rax:1'],['gpr:rax:1'])),
 ('mov-ax','6689d8',ex(cells('rbx',2),cells('rax',2),cells('rax',2))),
 ('mov-eax','89d8',ex(cells('rbx',4),cells('rax'),cells('rax'))),
 ('mov-imm','b878563412',ex((),cells('rax'),cells('rax'))),
 ('load','488b448b08',ex(['memory:any']+cells('rbx')+cells('rcx'),cells('rax'),cells('rax'))),
 ('store','488903',ex(cells('rax')+cells('rbx'),['memory:any'],())),
 ('load-dword','8b03',ex(['memory:any']+cells('rbx'),cells('rax'),cells('rax'))),
 ('store-dword','8985b8feffff',ex(cells('rbp')+cells('rax',4),['memory:any'],())),
 ('test64','4885db',dict(reject=False,uses_includes=cells('rbx'),must_excludes=['flag:af'])),
 ('test8','84c0',dict(reject=False,uses_includes=cells('rax',1),must_excludes=['flag:af'])),
 ('store-immediate','c70005000000',ex(cells('rax'),['memory:any'],())),
 ('store-sign-extended','48c70408ffffffff',ex(cells('rax')+cells('rcx'),['memory:any'],())),
 ('nop','90',ex()),
 ('cmov','480f45c3',ex(['flag:zf']+cells('rax')+cells('rbx'),cells('rax'),())),
 ('not','48f7d0',ex(cells('rax'),cells('rax'),cells('rax'))),
 ('movsx','480fbec0',ex(cells('rax',1),cells('rax'),cells('rax'))),
 ('movzx','0fb6c0',ex(cells('rax',1),cells('rax'),cells('rax'))),
 ('lea','488d4308',ex(cells('rbx'),cells('rax'),cells('rax'))),
 ('add','4801d8',ex(cells('rax')+cells('rbx'),cells('rax')+FLAGS,cells('rax')+FLAGS)),
 ('adc','4811d8',ex(cells('rax')+cells('rbx')+['flag:cf'],cells('rax')+FLAGS,cells('rax')+FLAGS)),
 ('cmp','4839d8',ex(cells('rax')+cells('rbx'),FLAGS,FLAGS)),
 ('inc','48ffc0',ex(cells('rax'),cells('rax')+[f for f in FLAGS if f!='flag:cf'],cells('rax')+[f for f in FLAGS if f!='flag:cf'])),
 ('push','50',ex(cells('rax')+cells('rsp'),cells('rsp')+['memory:any'],cells('rsp'))),
 ('pop','58',ex(cells('rsp')+['memory:any'],cells('rsp')+cells('rax'),cells('rsp')+cells('rax'))),
 ('jne','7502',ex(['flag:zf'])),
 ('jmp-direct','eb02',ex()),
 ('jmp-indirect','ffe0',ex(cells('rax'))),
 ('shift-zero','48c1e000',dict(reject=False,uses_excludes=['flag:cf'],must_excludes=FLAGS)),
 ('shift-variable','48d3e0',dict(reject=False,uses_includes=['gpr:rcx:0'],must_excludes=['flag:of'])),
 ('rip-load','488b0508000000',ex(['memory:any'],cells('rax'),cells('rax'))),
 ('call','e800000000',dict(reject=True)),('return','c3',dict(reject=True)),
 ('syscall','0f05',dict(reject=True)),('cpuid','0fa2',dict(reject=True)),('ud2','0f0b',dict(reject=True)),
 ('lock','f00118',dict(reject=True)),('rep','f3a4',dict(reject=True)),
 ('segment','64488b03',dict(reject=True)),('address-size','67488b03',dict(reject=True)),
]
def main():
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 runtime=ROOT/'tmp/bap-setup/stable';helper=ROOT/'target/ariadne-bap-lift'
 env={**os.environ,'LD_LIBRARY_PATH':f'{runtime}/usr/local/lib:{runtime}/usr/lib/x86_64-linux-gnu','XDG_STATE_HOME':str(runtime/'state'),'XDG_CACHE_HOME':str(runtime/'cache')}
 token=hashlib.sha256(b'bap-independent-effect-corpus-v1').hexdigest()
 request=f'ARIADNE-BAP-LIFT 1 linux-amd64 {token}\nbatch 0 {len(CASES)}\n'+''.join(f'0x{0x1000+i*32:016x} {hex}\n' for i,(_,hex,_) in enumerate(CASES))
 r=subprocess.run([helper,runtime/'usr/local/lib/bap'],input=request,text=True,capture_output=True,env=env,timeout=30)
 if r.returncode:raise SystemExit(r.stderr)
 lines=[json.loads(x) for x in r.stdout.splitlines()]
 assert lines[0]['lifter']=='legacy' and lines[-1]['count']==len(CASES) and len(lines)==len(CASES)+2
 rows=[dict(name=n,prefix=h,lift=l,expect=e) for (n,h,e),l in zip(CASES,lines[1:-1])]
 record=dict(schema='ariadne.bap-effect-corpus/v1',helperSha256=hashlib.sha256(helper.read_bytes()).hexdigest(),runtimeSha256=hashlib.sha256((runtime/'usr/local/lib/libbap.so.2.5.0').read_bytes()).hexdigest(),rows=rows)
 dest=Path(__file__).with_name('corpus.json');text=json.dumps(record,indent=2)+'\n'
 if a.check:
  if dest.read_text()!=text:raise SystemExit('native BIL corpus differs; review and regenerate explicitly')
 else:dest.write_text(text)
 print(f'{len(rows)} native BIL cases retained and matched' if a.check else f'Generated {dest}')
if __name__=='__main__':main()
