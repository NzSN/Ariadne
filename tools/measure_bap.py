#!/usr/bin/env python3
"""Release-build, same-host BAP-only costs and controlled coverage benefit."""
import argparse,csv,hashlib,io,json,os,platform,statistics,subprocess,tarfile,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from rust_layout import copy_sut, source_files
import real_capture_workload as real_case
from bap_workload_contract import WINDOWS_ARCHIVE_RELATIVE, WORKLOAD_SCHEMA, windows_case_error, windows_qualification
ROOT=Path(__file__).resolve().parents[1]
WINDOWS_CASE_PATH=ROOT/'evidence/Ariadne/bap-windows-workload-case.json'
WINDOWS_ARCHIVE_PATH=ROOT/WINDOWS_ARCHIVE_RELATIVE
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd,timeout=120):
 r=subprocess.run([str(x) for x in cmd],cwd=ROOT,capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 return r

def summary(values):return dict(median=statistics.median(values),min=min(values),max=max(values),samples=len(values))
def materialize_windows_capture(case,work):
 error=windows_case_error(case)
 if error:raise RuntimeError(error)
 archive=case['inputArchive'];capture=case['capture']
 if sha(WINDOWS_ARCHIVE_PATH)!=archive['sha256']:raise RuntimeError('Windows input archive hash mismatch')
 with tarfile.open(WINDOWS_ARCHIVE_PATH,'r:gz') as bundle:
  members=[member for member in bundle.getmembers() if member.name==archive['captureMember']]
  if len(members)!=1 or not members[0].isreg() or members[0].size!=capture['bytes']:raise RuntimeError('Windows input archive requires one regular capture member of the pinned size')
  with bundle.extractfile(members[0]) as stream:data=stream.read(capture['bytes']+1)
 if len(data)!=capture['bytes'] or hashlib.sha256(data).hexdigest()!=capture['sha256']:raise RuntimeError('Windows bundled capture hash or size mismatch')
 destination=Path(tempfile.mkdtemp(prefix='windows-input-',dir=work))/'capture.dmp'
 with destination.open('xb') as output:output.write(data)
 return destination
def sources():
 paths=source_files()
 for tree in ['src','src/input','src/reports','src/bap','src/investigation','src/bench','native/llvm_mc','native/bap']:
  paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.md')
 paths.update(ROOT/p for p in ['Cargo.toml','Cargo.lock','Cargo.toml','Cargo.lock','Cargo.toml','Cargo.lock','Cargo.toml','Cargo.lock','Cargo.toml','Cargo.lock','Cargo.toml','Cargo.lock','tools/measure_bap.py','tools/test_bap_workload.py','tools/bap_workload_contract.py','tools/test_bap_workload_contract.py','evidence/Ariadne/priority-1-real-capture-case.json','evidence/Ariadne/bap-windows-workload-case.json',WINDOWS_ARCHIVE_RELATIVE])
 paths.update(real_case.source_paths())
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def main():
 p=argparse.ArgumentParser(description=__doc__);windows_options=p.add_mutually_exclusive_group()
 windows_options.add_argument('--windows-dump',type=Path);windows_options.add_argument('--skip-windows',action='store_true',help='Run available implementation workloads without Windows qualification')
 p.add_argument('--output',type=Path);args=p.parse_args()
 source_hashes_before=sources()
 work=args.output or Path(tempfile.mkdtemp(prefix='ariadne-bap-workloads-'));work.mkdir(parents=True,exist_ok=True)
 cli=ROOT/'target/release/ariadne-minidump';bench=ROOT/'target/release/bap_minidump';decoder=ROOT/'target/ariadne-llvm-mc';helper=ROOT/'target/ariadne-bap-lift';runtime=ROOT/'tmp/bap-setup/stable'
 for exe in ['ariadne-minidump','bap_minidump']:
  run(['cargo','build','--offline','--locked','--release',*(['--features','bench'] if exe=='bap_minidump' else []),'--bin',exe])
 real_pin=real_case.load_case()
 cases=[('stage-b-linux',ROOT/'tests/input/fixtures/stage_b_linux.dmp','0x401000','0x401006',False),('stage-b-windows',ROOT/'tests/input/fixtures/stage_b_windows.dmp','0x7ff700001000','0x7ff700001006',False),('controlled-not',ROOT/'tests/input/fixtures/bap_precision_linux.dmp','0x401000','0x401006',False),('real-capture',real_case.selected_dump(real_pin,sha),real_pin['query']['entry_va'],real_pin['query']['seed_va'],True)]
 if sha(cases[-1][1])!=real_pin['capture']['sha256']:raise RuntimeError('active real-capture artifact hash mismatch')
 windows=json.loads(WINDOWS_CASE_PATH.read_text());windows_checked=not args.skip_windows
 error=windows_case_error(windows)
 if error:raise RuntimeError(error)
 if windows_checked:
  if source_hashes_before.get(WINDOWS_ARCHIVE_RELATIVE)!=windows['inputArchive']['sha256'] or sha(WINDOWS_ARCHIVE_PATH)!=windows['inputArchive']['sha256']:raise RuntimeError('Windows input archive hash mismatch')
  override=args.windows_dump or os.environ.get('ARIADNE_BAP_WINDOWS_DUMP')
  windows_dump=Path(override) if override else materialize_windows_capture(windows,work)
  if sha(windows_dump)!=windows['capture']['sha256'] or windows_dump.stat().st_size!=windows['capture']['bytes']:raise RuntimeError('Pinned controlled Windows artifact hash mismatch')
  cases.append((windows['id'],windows_dump,windows['query']['entry_va'],windows['query']['seed_va'],False))
 rows=[];stage_rows=[];records=[];analyses={}
 for label,dump,entry,seed,historical in cases:
  for backend in ['bap']:
   identity=None;report_hashes=None;count=None;measured=[];warmup_samples=[]
   for n in range(6):
    out=work/f'{label}-{backend}-{n}';timer=work/f'{label}-{backend}-{n}.time'
    cmd=[cli,dump,'--decoder',decoder,'--entry',entry,'--seed-exception-rip','--analysis-backend','rust','--output-dir',out]
    if backend=='bap':cmd+=['--bap-helper',helper,'--bap-runtime',runtime]
    start=time.perf_counter_ns();run(['/usr/bin/time','-f','%e,%M','-o',timer,*cmd]);ns=time.perf_counter_ns()-start
    wall,rss=timer.read_text().strip().split(',');report=json.loads((out/'report.json').read_text());h={name:sha(out/name) for name in ['report.json','report.txt','report.dot']}
    if identity is None:identity=report['identity'];report_hashes=h
    elif identity!=report['identity'] or report_hashes!=h:raise RuntimeError(f'nonrepeatable report: {label}/{backend}')
    if identity['artifact_sha256']!=sha(dump) or report['query']['entries']!=[f'0x{int(entry,16):016x}'] or report['query']['seeds']!=[f'0x{int(seed,16):016x}']:raise RuntimeError('query/artifact mismatch')
    counts={key:len(report['analysis'][key]) for key in ['decoded','edges','slice','obligations']}
    if label=='real-capture':real_case.validate_report(report,real_pin)
    if label==windows['id']:
     analysis=report['analysis'];producer=windows['query']['producer_va'];seed_va=windows['query']['seed_va']
     if len(analysis['decoded'])<64 or len(analysis['decoded'])!=windows['expectations']['decodedStarts'] or len(set(analysis['decoded']))!=len(analysis['decoded']) or seed_va not in analysis['decoded'] or analysis['missing_slice_seeds'] or producer not in analysis['slice']:raise RuntimeError('Windows producer/seed acceptance failed')
     seed_definitions=next(r['definitions'] for r in analysis['reaching'] if r['before']==seed_va)
     if not all(any(d['loc']==f'gpr:rcx:{i}' and d['site']==producer and d['origin']=='instruction' for d in seed_definitions) for i in range(8)):raise RuntimeError('Windows independent address-origin witness failed')
     decoded_preparation={va:[] for va in analysis['decoded']}
     for site in report['preparation']['sites']:
      if site.get('va') in decoded_preparation:decoded_preparation[site['va']].append(site)
     if any(len(sites)!=1 or sites[0].get('byte_source')!='captured' for sites in decoded_preparation.values()):raise RuntimeError('Windows decoded bytes lack captured provenance')
    statuses={}
    for site in report['preparation']['sites']:
     s=site.get('semantic',{}).get('status','unattempted');statuses[s]=statuses.get(s,0)+1
    row=dict(workload=label,backend=backend,run=n,warmup=n==0,elapsed_ms=ns/1e6,peak_rss_kib=int(rss),**counts);rows.append(row)
    if n:measured.append(row)
    else:warmup_samples.append(row['elapsed_ms'])
    analyses[(label,backend)]=report['analysis']
   stagecmd=[bench,dump,decoder,entry,seed,'6']
   if backend=='bap':stagecmd += [helper,runtime]
   phase=list(csv.DictReader(io.StringIO(run(stagecmd).stdout)))
   if len(phase)!=6:raise RuntimeError('phase benchmark count mismatch')
   for i,r in enumerate(phase):
    if r['artifact_sha256']!=identity['artifact_sha256'] or any(int(r[k])!=counts[k] for k in counts):raise RuntimeError('phase benchmark result binding mismatch')
    stage_rows.append(dict(workload=label,warmup=i==0,**r))
   record=dict(workload=label,backend=backend,historicalCapture=historical,artifactSha256=sha(dump),entry=entry,seed=seed,query={'entries':[f'0x{int(entry,16):016x}'],'seeds':[f'0x{int(seed,16):016x}']},identity=identity,reportSha256=report_hashes,counts=counts,semanticStatuses=statuses,warmupSamplesMs=warmup_samples,elapsedSamplesMs=[r['elapsed_ms'] for r in measured],elapsedMs=summary([r['elapsed_ms'] for r in measured]),peakRssKib=summary([r['peak_rss_kib'] for r in measured]),stageMs={k:summary([int(r[k])/1e6 for r in phase[1:]]) for k in phase[0] if k.endswith('_ns')})
   if label==windows['id']:record['captureKind']=windows['captureKind']
   records.append(record);print(label,backend,round(record['elapsedMs']['median'],2),'ms',counts,statuses,flush=True)
 for label in ['stage-b-linux','stage-b-windows']:
  if len(analyses[(label,'bap')]['decoded'])!=4 or len(analyses[(label,'bap')]['slice'])!=2:raise RuntimeError(f'independent Stage B result failed: {label}')
 if len(analyses[('controlled-not','bap')]['decoded'])!=4 or analyses[('controlled-not','bap')]['slice']!=['0x0000000000401000','0x0000000000401003','0x0000000000401006']:raise RuntimeError('independent controlled coverage/slice failed')
 active=analyses[('real-capture','bap')]
 if real_pin['query']['seed_va'] not in active['decoded'] or real_pin['query']['producer_va'] not in active['slice'] or active['missing_slice_seeds']:raise RuntimeError('active capture producer/seed witness failed')
 for name,data in [('cli.csv',rows),('stage.csv',stage_rows)]:
  with (work/name).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');w.writeheader();w.writerows(data)
 tools={str(p.relative_to(ROOT)):sha(p) for p in [cli,bench,decoder,helper,ROOT/'native/bap/toolchain.lock.json',ROOT/'tools/measure_bap.py']}
 stable=source_hashes_before==sources()
 record=dict(schema=WORKLOAD_SCHEMA,recordedUtc=datetime.now(timezone.utc).isoformat(),passed=stable,sourcesStable=stable,sourceHashes=source_hashes_before,host=platform.platform(),cpu=next((s.split(':',1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('model name')),None),logicalCpus=os.cpu_count(),profile='release',warmups=1,repeats=5,records=records,tools=tools,csvSha256={name:sha(work/name) for name in ['cli.csv','stage.csv']},coverageBenefit='BAP-only controlled NOT fixture: 4 decoded with exact 3-site slice; historical LLVM comparison is retained separately',semanticBackend='bap-only',llvmSemanticFallback=False,windowsWorkloadChecked=windows_checked,windowsWorkloadBudgetMs=None,windowsWorkloadTimingPolicy="unlimited")
 qualification=windows_qualification(record,windows)
 record.update(activeRealCaptureCase=real_pin,realLinuxCaptureExercised=real_pin['capture']['platform']=='linux',historicalLinuxCaptureExercised=False)
 record.update(windowsWorkloadQualification=qualification,windowsWorkloadTargetMet=qualification['targetMet'],defaultPromotionEligible=qualification['targetMet'],missing=[] if qualification['targetMet'] else [qualification['reason']])
 if windows_checked and not qualification['valid']:record['passed']=False
 (work/'report.json').write_text(json.dumps(record,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 if not stable:raise SystemExit('workload sources changed during validation')
 if not record['passed']:raise SystemExit('invalid Windows workload evidence: '+qualification['reason'])
if __name__=='__main__':main()
