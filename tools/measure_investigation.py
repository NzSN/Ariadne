#!/usr/bin/env python3
"""Source/tool-bound release measurements for the implemented explanation query."""
import argparse,csv,hashlib,io,json,os,platform,statistics,subprocess,tempfile,time
from pathlib import Path
from rust_layout import copy_sut, source_files
from investigation_budget import WORKLOAD_SCHEMA, WINDOWS_BUDGET_MS, windows_qualification
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
 paths=source_files()
 for tree in ['src','src/bap','src/input','src/reports','src/investigation','src/bench','native/bap','native/llvm_mc']:
  paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and p.suffix!='.md' and '__pycache__' not in p.parts)
 paths.update(ROOT/p for p in ['Cargo.toml', 'Cargo.lock', 'tools/measure_investigation.py', 'tools/investigation_budget.py', 'tools/test_investigation_budget.py', 'evidence/Ariadne/priority-1-real-capture-case.json', 'evidence/Ariadne/priority-4-real-capture-case.json'])
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def run(cmd):
 r=subprocess.run([str(a) for a in cmd],cwd=ROOT,text=True,capture_output=True,timeout=180)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 return r

def summary(xs):return dict(median=statistics.median(xs),min=min(xs),max=max(xs),samples=len(xs))
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--windows-dump',type=Path,default=os.environ.get('ARIADNE_PRIORITY4_DUMP'));args=parser.parse_args()
 before=sources();work=Path(tempfile.mkdtemp(prefix='ariadne-investigation-workload-'));cli=ROOT/'target/release/ariadne-minidump';bench=ROOT/'target/release/investigation';decoder=ROOT/'target/ariadne-llvm-mc'
 for b in ['ariadne-minidump','investigation']:
  run(['cargo','build','--offline','--locked','--release',*(['--features','bench'] if b=='investigation' else []),'--bin',b])
 cases=[('stage-b-linux',ROOT/'tests/input/fixtures/stage_b_linux.dmp','0x401000','0x401006',False),('stage-b-windows',ROOT/'tests/input/fixtures/stage_b_windows.dmp','0x7ff700001000','0x7ff700001006',False),('not-chain',ROOT/'tests/input/fixtures/bap_precision_linux.dmp','0x401000','0x401006',False),('real-linux',ROOT/'tmp/priority1/chromium-member-uaf.dmp','0x566817922dc5','0x566817922e42',True)]
 pin=json.loads((ROOT/'evidence/Ariadne/priority-1-real-capture-case.json').read_text())
 windows=json.loads((ROOT/'evidence/Ariadne/priority-4-real-capture-case.json').read_text())
 if args.windows_dump:
  if sha(args.windows_dump)!=windows['capture']['sha256']:raise RuntimeError('Windows capture hash mismatch')
  cases.append(('real-windows-98',args.windows_dump,windows['query']['entry_va'],windows['query']['seed_va'],True))
 if sha(ROOT/'tmp/priority1/chromium-member-uaf.dmp')!=pin['capture']['sha256']:raise RuntimeError('real case hash mismatch')
 rows=[];records=[];phases=[]
 for label,dump,entry,site,historical in cases:
  results={}
  for mode in ['base','explanation']:
   measured=[];warmup_samples=[];first_hash=None;first=None
   wanted_query={'entries':[f'0x{int(entry,16):016x}'],'seeds':[f'0x{int(site,16):016x}']}
   question={'site':wanted_query['seeds'][0],'memory_access':0} if mode=='explanation' else None
   for n in range(6):
    out=work/f'{label}-{mode}-{n}';metrics=work/f'{label}-{mode}-{n}.time'
    cmd=[cli,dump,'--decoder-reference',decoder,'--entry',entry,'--seed',site,'--output-dir',out]
    if mode=='explanation':cmd+=['--explain-fault-address',site,'--memory-access','0']
    start=time.perf_counter_ns();run(['/usr/bin/time','-f','%e,%M','-o',metrics,*cmd]);elapsed=(time.perf_counter_ns()-start)/1e6
    report=json.loads((out/'report.json').read_text());name='explanation.json' if mode=='explanation' else 'report.json';digest=sha(out/name)
    if report['identity']['artifact_sha256']!=sha(dump) or any(report['query'].get(k)!=v for k,v in wanted_query.items()):raise RuntimeError('CLI artifact/query mismatch')
    if first_hash is None:first_hash=digest;first=report
    elif first_hash!=digest or first['identity']!=report['identity']:raise RuntimeError('nonrepeatable output identity')
    rss=int(metrics.read_text().strip().split(',')[1]);row=dict(workload=label,mode=mode,run=n,warmup=n==0,elapsed_ms=elapsed,peak_rss_kib=rss,artifact_sha256=sha(dump));rows.append(row)
    if n:measured.append(row)
    else:warmup_samples.append(elapsed)
    if mode=='explanation':
     e=json.loads((out/name).read_text())
     if e['identity']['artifact_sha256']!=sha(dump) or e['identity']['query_id']!=report['identity']['query_id'] or e['question']!=question:raise RuntimeError('explanation artifact/query mismatch')
     producers={p['site'] for g in e['origins'] for p in g['producers']}
     expected=(windows if label=='real-windows-98' else pin)['query']['producer_va'] if historical else f'0x{int(entry,16)+(3 if label=="not-chain" else 0):016x}'
     if expected not in producers:raise RuntimeError('independent producer witness missing')
     if any(c['classification']=='observed' and c['assertion']['kind'] in ['possible_origin','dependency'] for c in e['claims']):raise RuntimeError('fabricated historical class')
   results[mode]=first['analysis'];records.append(dict(workload=label,mode=mode,historical=historical,artifactSha256=sha(dump),identity=first['identity'],query=first['query'],question=question,warmupSamplesMs=warmup_samples,elapsedSamplesMs=[r['elapsed_ms'] for r in measured],elapsedMs=summary([r['elapsed_ms'] for r in measured]),peakRssKiB=summary([r['peak_rss_kib'] for r in measured]),outputSha256=first_hash))
   print(label,mode,round(records[-1]['elapsedMs']['median'],2),'ms',flush=True)
  if results['base']!=results['explanation']:raise RuntimeError('explanation changed core analysis')
  phase=list(csv.DictReader(io.StringIO(run([bench,dump,decoder,entry,site,'6']).stdout)))
  if len(phase)!=6:raise RuntimeError('phase sample count')
  for i,p in enumerate(phase):
   if p['artifact_sha256']!=sha(dump):raise RuntimeError('phase artifact mismatch')
   phases.append(dict(workload=label,warmup=i==0,**p))
  records.append(dict(workload=label,mode='phase',stageMs={k:summary([int(r[k])/1e6 for r in phase[1:]]) for k in phase[0] if k.endswith('_ns')},claims=int(phase[1]['claims']),evidence=int(phase[1]['evidence']),gaps=int(phase[1]['gaps'])))
 for name,data in [('cli.csv',rows),('phase.csv',phases)]:
  with (work/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');w.writeheader();w.writerows(data)
 result=dict(schema=WORKLOAD_SCHEMA,profile='release',passed=before==sources() and all(sum(x['stageMs'][k]['median'] for k in ['binding_ns','explanation_ns','render_ns'])<=250 for x in records if x['mode']=='phase' and x['workload']=='real-linux'),sourcesStable=before==sources(),sourceHashes=before,tools={str(p.relative_to(ROOT)):sha(p) for p in [cli,bench,decoder,ROOT/'target/ariadne-bap-lift']},host=platform.platform(),warmups=1,repeats=5,records=records,csvSha256={p:sha(work/p) for p in ['cli.csv','phase.csv']},windows98Checked=args.windows_dump is not None,explanationPhaseBudgetMs=250,explanationPhaseBudgetMet=all(sum(x['stageMs'][k]['median'] for k in ['binding_ns','explanation_ns','render_ns'])<=250 for x in records if x['mode']=='phase' and x['workload']=='real-linux'),windows98BudgetMs=WINDOWS_BUDGET_MS,scope='BAP-only first question on both platform fixtures and retained controlled Linux capture; original Windows qualification is assessed separately')
 result['windows98Qualification']=windows_qualification(result,windows)
 (work/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
