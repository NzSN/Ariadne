#!/usr/bin/env python3
"""Owned v3 query measurements: explicit roots, opaque gaps and native parity."""
import argparse,hashlib,json,os,statistics,subprocess,time
from pathlib import Path
from compare_i5a_cli import without_verified_receipt
from with_mirrorrust_snapshot import active_identity
import check_bap_core
ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 before=check_bap_core.sources();manifest=json.loads((ROOT/'target/bap-core-native/manifest.json').read_text());rows=[]
 fixture_path=ROOT/'tests/input/fixtures/admission/manifest.json';fixtures=json.loads(fixture_path.read_text())['rows']
 executable=ROOT/'target/release/ariadne-minidump';tools={str(executable.relative_to(ROOT)):sha(executable),'target/bap-core-native/manifest.json':sha(ROOT/'target/bap-core-native/manifest.json')}
 for case in fixtures:
  dump=fixture_path.parent/case['name'];assert sha(dump)==case['sha256'];case_out=out/case['name'];case_out.mkdir();samples=[];last={}
  for backend in ['rust','bap']:
   for run in range(6):
    bundle=case_out/f'{backend}-{run}';start=time.perf_counter_ns()
    command=[executable,dump,'--decoder-reference',ROOT/'target/ariadne-llvm-mc','--entry',case['entry'],'--seed',case['seed'],'--analysis-backend',backend,'--output-dir',bundle]
    r=subprocess.run([str(x) for x in command],cwd=ROOT,capture_output=True,text=True,timeout=120)
    elapsed=(time.perf_counter_ns()-start)/1e6
    if r.returncode:raise RuntimeError(r.stderr)
    report=json.loads((bundle/'report.json').read_text());assert len(report['analysis']['decoded'])==case['expectedDecoded']
    assert report['query']['entries']==[case['entry']] and report['query']['seeds']==[case['seed']]
    if case['kind']=='opaque':
     opaque=f'0x{int(case["entry"],16)+3:016x}';site=next(s for s in report['preparation']['sites'] if s['va']==opaque)
     assert site['semantic']['status']=='opaque-ordinary' and 'unsupported-data-effects' in site['semantic']['gaps']
     assert not any(g['va']==opaque and g['reason']=='unsupported_control' for g in report['preparation']['gaps'])
     reaching=next(r for r in report['analysis']['reaching'] if r['before']==case['seed'])
     for cell in range(8):assert {d['site'] for d in reaching['definitions'] if d['loc']==f'gpr:rcx:{cell}'}=={case['entry'],opaque}
    text=(bundle/'report.txt').read_text();dot=(bundle/'report.dot').read_text()
    normalized=without_verified_receipt(report,text,dot,manifest) if backend=='bap' else (report,text,dot)
    if backend in last:assert normalized==last[backend]
    last[backend]=normalized;samples.append(dict(backend=backend,run=run,warmup=run==0,cliMs=elapsed,reportBytes=sum(f.stat().st_size for f in bundle.iterdir()),reportSha256={f.name:sha(f) for f in bundle.iterdir()}))
  assert last['rust']==last['bap'];medians={b:statistics.median(s['cliMs'] for s in samples if s['backend']==b and not s['warmup']) for b in ['rust','bap']}
  rows.append(dict(case=case,samples=samples,cliMedianMs=medians,nativeReferenceEqual=True));print(case['name'],medians,flush=True)
 record=dict(schema='ariadne.bap-admission-workloads/v1',passed=before==check_bap_core.sources(),sourcesStable=before==check_bap_core.sources(),sourceHashes=before,tools=tools,qualificationEnvironment=active_identity(),helperManifest=manifest,fixtureManifestSha256=sha(fixture_path),warmups=1,repeats=5,records=rows,timingPolicy='BAP unlimited; existing I4/I5 fixed budgets remain separate',captureKind='owned synthetic minidumps, not external Electron captures')
 (out/'report.json').write_text(json.dumps(record,indent=2)+'\n');print('Report:',out/'report.json',flush=True)
 if not record['passed']:raise SystemExit(1)
if __name__=='__main__':main()
