#!/usr/bin/env python3
"""Source/tool-bound I5a fixture measurements against the predeclared contract."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time
from rust_layout import source_files

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sources():
    paths=source_files()
    paths.update(ROOT/p for p in ['tools/measure_i5a.py','tools/rust_layout.py','native/bap/toolchain.lock.json'])
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def run(command,env):
    result=subprocess.run([str(x) for x in command],cwd=ROOT,env=env,text=True,capture_output=True,timeout=240)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    return result

def main():
    before=sources();work=Path(tempfile.mkdtemp(prefix='ariadne-i5a-measurement-'))
    env={**os.environ,'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
    contract=json.loads((ROOT/'tests/input/fixtures/i5a/performance.json').read_text())
    cases={r['name']:r for r in json.loads((ROOT/'tests/input/fixtures/i5a/manifest.json').read_text())['cases']}
    for binary,flags in [('ariadne-minidump',[]),('i5a',['--features','bench'])]:
        run(['cargo','build','--offline','--locked','--release',*flags,'--bin',binary],env)
    cli=ROOT/'target/release/ariadne-minidump';bench=ROOT/'target/release/i5a';decoder=ROOT/'target/ariadne-llvm-mc'
    tool_paths=[cli,bench,decoder,ROOT/'target/ariadne-bap-lift',ROOT/'tmp/bap-setup/stable/usr/local/lib/libbap.so.2.5.0']
    tools_before={str(p.relative_to(ROOT)):sha(p) for p in tool_paths}
    rows=[];phases=[];records=[]
    print('I5a measurement artifacts:',work,flush=True)
    for name in contract['cases']:
        case=cases[name];dump=ROOT/'tests/input/fixtures/i5a'/f'{name}.dmp'
        if sha(dump)!=case['sha256']:raise RuntimeError('fixture identity mismatch')
        modes={};expected_core=None;question={'site':f"0x{case['site']:016x}",'memory_access':0}
        for mode in ['base','assessment']:
            samples=[];outputs=None
            for n in range(contract['warmups']+contract['repeats']):
                out=work/f'{name}-{mode}-{n}';timer=work/f'{name}-{mode}-{n}.time'
                command=[cli,dump,'--decoder-reference',decoder,'--entry',f"{case['site']:x}",'--seed',f"{case['site']:x}",'--output-dir',out]
                if mode=='assessment':command+=['--assess-zero-address',f"{case['site']:x}",'--memory-access','0']
                start=time.perf_counter_ns();run(['/usr/bin/time','-f','%e,%M','-o',timer,*command],env);elapsed=(time.perf_counter_ns()-start)/1e6
                hashes={p.name:sha(p) for p in out.iterdir() if p.is_file()}
                if outputs is not None and outputs!=hashes:raise RuntimeError('nonrepeatable output')
                outputs=hashes
                core={p:hashes[p] for p in ['report.txt','report.json','report.dot']}
                if expected_core is None:expected_core=core
                elif expected_core!=core:raise RuntimeError('assessment changed original report bytes')
                report=json.loads((out/'report.json').read_text())
                if report['identity']['artifact_sha256']!=case['sha256'] or report['query']['entries']!=[question['site']] or report['query']['seeds']!=[question['site']]:raise RuntimeError('query identity changed')
                if mode=='assessment':
                    result=json.loads((out/'zero-address-assessment.json').read_text())
                    if result['conclusion']!=case['outcome'] or result['question']!=question or result['identity']['artifact_sha256']!=case['sha256']:raise RuntimeError('independent assessment expectation failed')
                rss=int(timer.read_text().strip().split(',')[1]);rows.append(dict(case=name,mode=mode,run=n,warmup=n<contract['warmups'],elapsed_ms=elapsed,rss_kib=rss))
                if n>=contract['warmups']:samples.append(elapsed)
            modes[mode]={'samplesMs':samples,'medianMs':statistics.median(samples),'minMs':min(samples),'maxMs':max(samples),'outputHashes':outputs}
        raw=list(csv.DictReader(io.StringIO(run([bench,dump,decoder,f"{case['site']:x}",f"{case['site']:x}",str(contract['warmups']+contract['repeats'])],env).stdout)))
        if len(raw)!=contract['warmups']+contract['repeats'] or any(r['artifact_sha256']!=case['sha256'] for r in raw):raise RuntimeError('phase samples not bound')
        if len({r['output_sha256'] for r in raw})!=1:raise RuntimeError('phase output not repeatable')
        samples=[int(r['total_ns'])/1e6 for r in raw[contract['warmups']:]]
        for r in raw:phases.append(dict(case=name,**r))
        passed=statistics.median(samples)<=contract['phaseMedianBudgetMs'] and modes['assessment']['medianMs']<=contract['cliMedianBudgetMs']
        records.append(dict(case=name,artifactSha256=case['sha256'],modes=modes,phaseSamplesMs=samples,phaseMedianMs=statistics.median(samples),passed=passed))
        print(name,'PASS' if passed else 'OVER BUDGET',round(modes['assessment']['medianMs'],2),'ms CLI;',round(statistics.median(samples),3),'ms phases',flush=True)
    for name,data in [('cli.csv',rows),('phase.csv',phases)]:
        with (work/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');writer.writeheader();writer.writerows(data)
    tools_after={str(p.relative_to(ROOT)):sha(p) for p in tool_paths};stable=before==sources()
    report=dict(schema='ariadne.i5a-fixture-measurements/v1',passed=stable and tools_before==tools_after and all(r['passed'] for r in records),sourcesStable=stable,toolsStable=tools_before==tools_after,sourceHashes=before,tools=tools_after,contract=contract,host=platform.platform(),records=records,csvSha256={p:sha(work/p) for p in ['cli.csv','phase.csv']},controlledRealWindowsAcceptancePassed=False,originalWindowsI4AcceptancePassed=False,scope=contract['scope'])
    (work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
    raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()
