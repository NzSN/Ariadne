#!/usr/bin/env python3
"""Owned v3 query measurements: explicit roots, opaque gaps and native parity."""
import argparse,csv,hashlib,io,json,os,statistics,subprocess,time
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
 build=subprocess.run(['cargo','build','--offline','--locked','--release','--features','bench','--bin','bap_minidump'],cwd=ROOT,capture_output=True,text=True)
 if build.returncode:raise RuntimeError(build.stdout+build.stderr)
 executable=ROOT/'target/release/ariadne-minidump';benchmark=ROOT/'target/release/bap_minidump'
 tools={str(p.relative_to(ROOT)):sha(p) for p in [executable,benchmark,ROOT/'target/bap-core-native/manifest.json',ROOT/'target/ariadne-bap-lift',ROOT/'target/ariadne-llvm-mc']}
 for case in fixtures:
  dump=fixture_path.parent/case['name'];assert sha(dump)==case['sha256'];case_out=out/case['name'];case_out.mkdir();samples=[];last={};phases={};limits=None;raw_digest=None;raw_bytes=None
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
    current_limits={key:report['input'][key] for key in ['open_limits','prepare_limits']}
    if limits is None:limits=current_limits
    else:assert limits==current_limits
    if backend=='rust':
     raw=b''.join((bundle/name).read_bytes() for name in ['report.txt','report.dot','report.json'])
     current_digest=hashlib.sha256(raw).hexdigest()
     if raw_digest is None:raw_digest=current_digest;raw_bytes=len(raw)
     else:assert raw_digest==current_digest and raw_bytes==len(raw)
   command=[benchmark,dump,ROOT/'target/ariadne-llvm-mc',case['entry'],case['seed'],'6','--analysis-backend',backend]
   measured=subprocess.run([str(x) for x in command],cwd=ROOT,capture_output=True,text=True,timeout=120)
   (case_out/(backend+'-phases.csv')).write_text(measured.stdout);(case_out/(backend+'-phases.stderr')).write_text(measured.stderr)
   if measured.returncode:raise RuntimeError(measured.stderr)
   phase=list(csv.DictReader(io.StringIO(measured.stdout)));assert len(phase)==6
   for index,row in enumerate(phase):
    assert row['artifact_sha256']==case['sha256'] and row['analysis_backend']==backend and int(row['run'])==index
    assert row['analysis_helper_sha256']==(manifest['helper_sha256'] if backend=='bap' else '')
    assert row['output_sha256']==raw_digest and int(row['output_bytes'])==raw_bytes
    for key in ['decoded','edges','slice','obligations']:assert int(row[key])==len(report['analysis'][key])
    assert int(row['total_ns'])==sum(int(row[key]) for key in ['open_ns','backend_setup_ns','prepare_ns','shutdown_ns','analysis_ns','render_ns'])
   phases[backend]=dict(samples=phase,stageMedianMs={key:statistics.median(int(row[key])/1e6 for row in phase[1:]) for key in phase[0] if key.endswith('_ns')},analysisBackend=backend,rawReportSha256=raw_digest,rawReportBytes=raw_bytes)
  assert last['rust']==last['bap'];medians={b:statistics.median(s['cliMs'] for s in samples if s['backend']==b and not s['warmup']) for b in ['rust','bap']}
  rows.append(dict(case=case,samples=samples,cliMedianMs=medians,nativeReferenceEqual=True,limits=limits,phases=phases));print(case['name'],medians,flush=True)
 tools_stable=all(sha(ROOT/name)==digest for name,digest in tools.items())
 record=dict(schema='ariadne.bap-admission-workloads/v2',passed=before==check_bap_core.sources() and tools_stable,sourcesStable=before==check_bap_core.sources(),toolsStable=tools_stable,sourceHashes=before,tools=tools,qualificationEnvironment=active_identity(),helperManifest=manifest,fixtureManifestSha256=sha(fixture_path),warmups=1,repeats=5,records=rows,timingPolicy='BAP unlimited; existing I4/I5 fixed budgets remain separate',captureKind='owned synthetic minidumps, not external Electron captures',phaseRenderScope='base text/DOT/JSON before CLI backend-receipt decoration; CLI report sizes include the receipt')
 (out/'report.json').write_text(json.dumps(record,indent=2)+'\n');print('Report:',out/'report.json',flush=True)
 if not record['passed']:raise SystemExit(1)
if __name__=='__main__':main()
