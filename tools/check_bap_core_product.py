#!/usr/bin/env python3
"""Independent output checks and native/reference release workload comparison."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
from measure_bap import materialize_windows_capture, WINDOWS_CASE_PATH
import real_capture_workload as real_case

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def unique(pairs):
 result={}
 for k,v in pairs:
  if k in result:raise ValueError('duplicate JSON field')
  result[k]=v
 return result
def read(text):return json.loads(text,object_pairs_hook=unique)
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--helper-dir',type=Path,default=ROOT/'target/bap-core-stage2');parser.add_argument('--expect-default',action='store_true')
 args=parser.parse_args();work=args.output.resolve();work.mkdir(parents=True,exist_ok=True)
 pin=read(WINDOWS_CASE_PATH.read_text());windows=materialize_windows_capture(pin,work)
 real_pin=real_case.load_case()
 cases=[('linux',ROOT/'tests/input/fixtures/stage_b_linux.dmp','0x401000','0x401006',4),
 ('windows',ROOT/'tests/input/fixtures/stage_b_windows.dmp','0x7ff700001000','0x7ff700001006',4),
 ('not',ROOT/'tests/input/fixtures/bap_precision_linux.dmp','0x401000','0x401006',4),
 ('real-capture',real_case.selected_dump(real_pin),real_pin['query']['entry_va'],real_pin['query']['seed_va'],real_pin['expectations']['decodedStarts']),
 ('windows98',windows,pin['query']['entry_va'],pin['query']['seed_va'],98)]
 assert sha(cases[3][1])==real_pin['capture']['sha256']
 assert sha(windows)==pin['capture']['sha256']
 executable=ROOT/'target/release/ariadne-minidump';manifest=read((args.helper_dir/'manifest.json').read_text())
 env={**os.environ,'ARIADNE_BAP_CORE_DIR':str(args.helper_dir.resolve())}
 rows=[]
 for name,dump,entry,seed,count in cases:
  reference=None;native_outputs=None
  for backend in ['rust','bap']:
   samples=[];warmup=None;expected=None
   for n in range(6):
    out=work/f'{name}-{backend}-{n}'
    command=[executable,dump,'--decoder-reference',ROOT/'target/ariadne-llvm-mc','--entry',entry,'--seed',seed,
     '--bap-helper',ROOT/'target/ariadne-bap-lift','--bap-runtime',ROOT/'tmp/bap-setup/stable','--analysis-backend',backend,'--output-dir',out]
    start=time.monotonic_ns();r=subprocess.run([str(x) for x in command],cwd=ROOT,env=env,text=True,capture_output=True,timeout=600);elapsed=(time.monotonic_ns()-start)/1e6
    (work/f'{name}-{backend}-{n}.stderr').write_text(r.stderr)
    if r.returncode:raise RuntimeError(r.stderr)
    if n:samples.append(elapsed)
    else:warmup=elapsed
    report=read((out/'report.json').read_text());text=(out/'report.txt').read_text();dot=(out/'report.dot').read_text()
    identity=report['identity'];query=report['query'];analysis=report['analysis']
    assert identity['artifact_sha256']==sha(dump)
    assert query['entries']==[f'0x{int(entry,16):016x}'] and query['seeds']==[f'0x{int(seed,16):016x}']
    assert len(analysis['decoded'])==count and len(set(analysis['decoded']))==count
    assert not analysis['missing_slice_seeds'] and f'0x{int(seed,16):016x}' in analysis['slice']
    assert read(next(line[10:] for line in text.splitlines() if line.startswith('identity: ')))==identity
    assert read(next(line[13:] for line in dot.splitlines() if line.startswith('// identity: ')))==identity
    assert 'digraph' in dot
    if name=='real-capture':real_case.validate_report(report,real_pin)
    if backend=='bap':
     receipt=report.pop('analysis_backend');assert receipt['schema']=='ariadne.analysis-backend/v1' and receipt['backend']=='bap'
     assert receipt['profile']=='captured-fixed-input/v1' and receipt['build']==manifest and receipt['snapshot']==identity['snapshot_id']
     assert read(next(line[len('analysis backend: '):] for line in text.splitlines() if line.startswith('analysis backend: ')))==receipt
     assert read(dot.splitlines()[0][len('// analysis backend: '):])==receipt
     text=''.join(line for line in text.splitlines(True) if not line.startswith('analysis backend: '))
     dot=''.join(dot.splitlines(True)[1:])
    outputs=(report,text,dot)
    if expected is None:expected=outputs
    else:assert outputs==expected,'nonrepeatable product reports'
    if backend=='bap':assert outputs==reference,'native/reference report difference'
    if name=='windows98':
     producer=pin['query']['producer_va'];assert producer in analysis['slice']
     definitions=next(row['definitions'] for row in analysis['reaching'] if row['before']==seed)
     assert all(any(d['loc']==f'gpr:rcx:{i}' and d['site']==producer and d['origin']=='instruction' for d in definitions) for i in range(8))
     sites={s['va']:s for s in report['preparation']['sites']}
     assert all(sites[a]['byte_source']=='captured' for a in analysis['decoded'])
   if backend=='rust':reference=expected
   else:native_outputs=out
   rows.append({'case':name,'backend':backend,'artifactSha256':sha(dump),'decoded':count,'warmupMs':warmup,'samplesMs':samples,'medianMs':statistics.median(samples)})
   print(f'{name}/{backend}: {statistics.median(samples):.2f} ms, {count} starts',flush=True)
  if args.expect_default:
   out=work/f'{name}-default';command=[executable,dump,'--decoder-reference',ROOT/'target/ariadne-llvm-mc','--entry',entry,'--seed',seed,'--bap-helper',ROOT/'target/ariadne-bap-lift','--bap-runtime',ROOT/'tmp/bap-setup/stable','--output-dir',out]
   r=subprocess.run([str(x) for x in command],cwd=ROOT,env=env,capture_output=True,timeout=600)
   assert r.returncode==0,r.stderr
   assert all((out/f).read_bytes()==(native_outputs/f).read_bytes() for f in ['report.json','report.txt','report.dot'])
 record={'activeRealCaptureCase':real_pin,'realLinuxCaptureExercised':real_pin['capture']['platform']=='linux','historicalLinuxCaptureExercised':False,'schema':'ariadne.bap-core-product/v1','passed':True,'timingPolicy':'unlimited','samples':rows,'defaultNativeVerified':args.expect_default,'executableSha256':sha(executable),'helperManifest':manifest,'windowsPinSha256':sha(WINDOWS_CASE_PATH),'scope':'five captured release workloads; one warm-up and five measured samples per backend; complete report equality after verified backend receipt removal'}
 (work/'result.json').write_text(json.dumps(record,indent=2)+'\n')
if __name__=='__main__':main()
