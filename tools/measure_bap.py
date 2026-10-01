#!/usr/bin/env python3
"""Release-build, same-host optional-backend costs and controlled coverage benefit."""
import argparse,csv,hashlib,io,json,os,platform,statistics,subprocess,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd,timeout=120):
 r=subprocess.run([str(x) for x in cmd],cwd=ROOT,capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 return r

def summary(values):return dict(median=statistics.median(values),min=min(values),max=max(values),samples=len(values))
def sources():
 paths=set()
 for tree in ['src','input/src','reports/src','bap/src','investigation/src','bench/src','native/llvm_mc','native/bap']:
  paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.md')
 paths.update(ROOT/p for p in ['Cargo.toml','Cargo.lock','input/Cargo.toml','input/Cargo.lock','reports/Cargo.toml','reports/Cargo.lock','bap/Cargo.toml','bap/Cargo.lock','investigation/Cargo.toml','investigation/Cargo.lock','bench/Cargo.toml','bench/Cargo.lock','tools/measure_bap.py','docs/Ariadne/priority-1-real-capture-case.json','docs/Ariadne/priority-4-real-capture-case.json'])
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def main():
 before=sources()
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--windows-dump',type=Path,default=os.environ.get('ARIADNE_PRIORITY4_DUMP'));p.add_argument('--output',type=Path);args=p.parse_args()
 work=args.output or Path(tempfile.mkdtemp(prefix='ariadne-bap-workloads-'));work.mkdir(parents=True,exist_ok=True)
 cli=ROOT/'input/target/release/ariadne-minidump';bench=ROOT/'bench/target/release/bap_minidump';decoder=ROOT/'target/ariadne-llvm-mc';helper=ROOT/'target/ariadne-bap-lift';runtime=ROOT/'tmp/bap-setup/stable'
 for manifest,exe in [('input/Cargo.toml','ariadne-minidump'),('bench/Cargo.toml','bap_minidump')]:run(['cargo','build','--offline','--locked','--release','--manifest-path',manifest,'--bin',exe])
 cases=[('stage-b-linux',ROOT/'input/tests/fixtures/stage_b_linux.dmp','0x401000','0x401006',False),('stage-b-windows',ROOT/'input/tests/fixtures/stage_b_windows.dmp','0x7ff700001000','0x7ff700001006',False),('controlled-not',ROOT/'input/tests/fixtures/bap_precision_linux.dmp','0x401000','0x401006',False),('real-linux-34',ROOT/'tmp/priority1/chromium-member-uaf.dmp','0x566817922dc5','0x566817922e42',True)]
 pinned_linux=json.loads((ROOT/'docs/Ariadne/priority-1-real-capture-case.json').read_text())
 expected_linux=pinned_linux['capture']['sha256']
 if sha(cases[-1][1])!=expected_linux:raise RuntimeError('real Linux artifact hash mismatch')
 windows=json.loads((ROOT/'docs/Ariadne/priority-4-real-capture-case.json').read_text());windows_checked=args.windows_dump is not None
 if windows_checked:
  if sha(args.windows_dump)!=windows['capture']['sha256'] or args.windows_dump.stat().st_size!=windows['capture']['bytes']:raise RuntimeError('98-instruction Windows artifact hash mismatch')
  cases.append(('real-windows-98',args.windows_dump,windows['query']['entry_va'],windows['query']['seed_va'],True))
 rows=[];stage_rows=[];records=[];analyses={}
 for label,dump,entry,seed,historical in cases:
  for backend in ['bap']:
   identity=None;report_hashes=None;count=None;measured=[]
   for n in range(6):
    out=work/f'{label}-{backend}-{n}';timer=work/f'{label}-{backend}-{n}.time'
    cmd=[cli,dump,'--decoder',decoder,'--entry',entry,'--seed-exception-rip','--output-dir',out]
    if backend=='bap':cmd+=['--bap-helper',helper,'--bap-runtime',runtime]
    start=time.perf_counter_ns();run(['/usr/bin/time','-f','%e,%M','-o',timer,*cmd]);ns=time.perf_counter_ns()-start
    wall,rss=timer.read_text().strip().split(',');report=json.loads((out/'report.json').read_text());h={name:sha(out/name) for name in ['report.json','report.txt','report.dot']}
    if identity is None:identity=report['identity'];report_hashes=h
    elif identity!=report['identity'] or report_hashes!=h:raise RuntimeError(f'nonrepeatable report: {label}/{backend}')
    if identity['artifact_sha256']!=sha(dump) or report['query']['entries']!=[f'0x{int(entry,16):016x}'] or report['query']['seeds']!=[f'0x{int(seed,16):016x}']:raise RuntimeError('query/artifact mismatch')
    counts={key:len(report['analysis'][key]) for key in ['decoded','edges','slice','obligations']}
    if label=='real-windows-98':
     analysis=report['analysis'];producer=windows['query']['producer_va'];seed_va=windows['query']['seed_va']
     if len(analysis['decoded'])<64 or seed_va not in analysis['decoded'] or analysis['missing_slice_seeds'] or producer not in analysis['slice']:raise RuntimeError('Windows producer/seed acceptance failed')
     before=next(r['definitions'] for r in analysis['reaching'] if r['before']==seed_va)
     if not all(any(d['loc']==f'gpr:rcx:{i}' and d['site']==producer and d['origin']=='instruction' for d in before) for i in range(8)):raise RuntimeError('Windows independent address-origin witness failed')
     if any(site['byte_source']!='captured' for site in report['preparation']['sites'] if site['va'] in analysis['decoded']):raise RuntimeError('Windows decoded bytes lack captured provenance')
    statuses={}
    for site in report['preparation']['sites']:
     s=site.get('semantic',{}).get('status','unattempted');statuses[s]=statuses.get(s,0)+1
    row=dict(workload=label,backend=backend,run=n,warmup=n==0,elapsed_ms=ns/1e6,peak_rss_kib=int(rss),**counts);rows.append(row)
    if n:measured.append(row)
    analyses[(label,backend)]=report['analysis']
   stagecmd=[bench,dump,decoder,entry,seed,'6']
   if backend=='bap':stagecmd += [helper,runtime]
   phase=list(csv.DictReader(io.StringIO(run(stagecmd).stdout)))
   if len(phase)!=6:raise RuntimeError('phase benchmark count mismatch')
   for i,r in enumerate(phase):
    if r['artifact_sha256']!=identity['artifact_sha256'] or any(int(r[k])!=counts[k] for k in counts):raise RuntimeError('phase benchmark result binding mismatch')
    stage_rows.append(dict(workload=label,warmup=i==0,**r))
   record=dict(workload=label,backend=backend,historicalCapture=historical,artifactSha256=sha(dump),entry=entry,seed=seed,identity=identity,reportSha256=report_hashes,counts=counts,semanticStatuses=statuses,elapsedMs=summary([r['elapsed_ms'] for r in measured]),peakRssKib=summary([r['peak_rss_kib'] for r in measured]),stageMs={k:summary([int(r[k])/1e6 for r in phase[1:]]) for k in phase[0] if k.endswith('_ns')})
   records.append(record);print(label,backend,round(record['elapsedMs']['median'],2),'ms',counts,statuses,flush=True)
 for label in ['stage-b-linux','stage-b-windows']:
  if len(analyses[(label,'bap')]['decoded'])!=4 or len(analyses[(label,'bap')]['slice'])!=2:raise RuntimeError(f'independent Stage B result failed: {label}')
 if len(analyses[('controlled-not','bap')]['decoded'])!=4 or analyses[('controlled-not','bap')]['slice']!=['0x0000000000401000','0x0000000000401003','0x0000000000401006']:raise RuntimeError('independent controlled coverage/slice failed')
 linux=analyses[('real-linux-34','bap')]
 if '0x0000566817922e42' not in linux['decoded'] or '0x0000566817922de6' not in linux['slice'] or linux['missing_slice_seeds']:raise RuntimeError('real Linux producer/seed witness failed')
 for name,data in [('cli.csv',rows),('stage.csv',stage_rows)]:
  with (work/name).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');w.writeheader();w.writerows(data)
 tools={str(p.relative_to(ROOT)):sha(p) for p in [cli,bench,decoder,helper,ROOT/'native/bap/toolchain.lock.json',ROOT/'tools/measure_bap.py']}
 target_met=next((r['elapsedMs']['median']<=2000 for r in records if r['workload']=='real-windows-98' and r['backend']=='bap'),False)
 record=dict(schema='ariadne.bap-workloads/v1',recordedUtc=datetime.now(timezone.utc).isoformat(),passed=before==sources(),sourcesStable=before==sources(),sourceHashes=before,host=platform.platform(),cpu=next((s.split(':',1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('model name')),None),logicalCpus=os.cpu_count(),profile='release',warmups=1,repeats=5,records=records,tools=tools,csvSha256={name:sha(work/name) for name in ['cli.csv','stage.csv']},coverageBenefit='BAP-only controlled NOT fixture: 4 decoded with exact 3-site slice; historical LLVM comparison is retained separately',semanticBackend='bap-only',llvmSemanticFallback=False,windows98Checked=windows_checked,windows98BudgetMs=2000,windows98TargetMet=target_met,defaultPromotionEligible=windows_checked and target_met,missing=[] if windows_checked else ['hash-pinned Windows 98-instruction artifact unavailable; no fresh acceptance or default promotion claim'])
 (work/'report.json').write_text(json.dumps(record,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 if not record['passed']:raise SystemExit('workload sources changed during validation')
if __name__=='__main__':main()
