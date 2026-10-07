#!/usr/bin/env python3
"""Measure native-default I5b fixtures or independently inspected real captures."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
from i5b_contract import ROOT, contract, environment, sha, sources, tools, validate_measurements
from i5a_native_contract import validate_backend_receipt,native_manifest
from with_mirrorrust_snapshot import active_identity


def run(command):
    result=subprocess.run([str(x) for x in command],cwd=ROOT,env=environment(),capture_output=True,text=True,timeout=120)
    if result.returncode: raise RuntimeError(result.stdout+result.stderr)
    return result.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--captures',type=Path)
    args=parser.parse_args()
    work=args.output.resolve();work.mkdir(parents=True,exist_ok=False)
    before=sources(); tools_before=tools(); frozen=contract()
    if args.captures:
        sys.path.insert(0,str(ROOT/'native/crashpad-demo'))
        from inspect_i5b import inspect
        cases=[]
        for label in ['positive','refuted','unknown']:
            for mode in ['partial','full']:
                name=label+'-'+mode; folder=args.captures/name
                inspection=inspect(folder)
                expected={'positive':'consistent_with_evidence','refuted':'refuted_under_premises','unknown':'unknown'}[label]
                if inspection['mode']!=mode or inspection['expectedConclusion']!=expected:
                    raise ValueError('controlled recipe does not match the declared corpus position')
                (work/(name+'-inspection.json')).write_text(json.dumps(inspection,indent=2)+'\n')
                capture=json.loads((folder/'capture.json').read_text())
                if capture['uploadsEnabled'] is not False or capture['childEnvironment']['policy']!='minimal-windows/v1':
                    raise ValueError('controlled capture has a different environment policy')
                cases.append(dict(name=name,dump=folder/'capture.dmp',entry=inspection['query']['entry'],
                    site=inspection['query']['site'],expected=expected,inspection=inspection))
    else:
        manifest=json.loads((ROOT/'tests/input/fixtures/i5b/manifest.json').read_text())
        indexed={r['name']:r for r in manifest['cases']}
        cases=[]
        for name in frozen['fixtureCases']:
            row=indexed[name];dump=ROOT/f'tests/input/fixtures/i5b/{name}.dmp'
            if sha(dump)!=row['sha256']: raise ValueError('fixture digest differs')
            cases.append(dict(name=name,dump=dump,entry=f"0x{row['site']:016x}",site=f"0x{row['site']:016x}",expected=row['outcome']))
    rows=[]
    for case in cases:
        name=case['name'];samples=[];hashes=None;report=None;assessment=None
        for n in range(frozen['warmups']+frozen['measuredRepeats']):
            out=work/f'{name}-{n}'
            command=[ROOT/'target/release/ariadne-minidump',case['dump'],'--decoder-reference',ROOT/'target/ariadne-llvm-mc',
                '--entry',case['entry'],'--assess-zero-base-offset',case['site'],'--memory-access','0','--output-dir',out]
            start=time.perf_counter_ns();run(command);elapsed=(time.perf_counter_ns()-start)/1e6
            current={p.name:sha(p) for p in out.iterdir()}
            if hashes is not None and current!=hashes: raise ValueError('nonrepeatable output')
            hashes=current;report=json.loads((out/'report.json').read_text());assessment=json.loads((out/'zero-base-offset-assessment.json').read_text())
            if report['identity']['artifact_sha256']!=sha(case['dump']): raise ValueError('measured artifact differs')
            receipt=validate_backend_receipt(report,native_manifest())
            samples.append(dict(run=n,elapsedMs=elapsed,outputHashes=current,backendReceipt=receipt,
                artifactSha256=report['identity']['artifact_sha256']))
        phase=run([ROOT/'target/release/i5b',case['dump'],ROOT/'target/ariadne-llvm-mc',case['entry'],case['site'],6])
        (work/(name+'-phases.csv')).write_text(phase)
        phase_rows=list(csv.DictReader(io.StringIO(phase)))
        last=work/f'{name}-5'
        phase_hash=hashlib.sha256(b''.join((last/('zero-base-offset-assessment.'+fmt)).read_bytes() for fmt in ['txt','json','dot'])).hexdigest()
        rows.append(dict(case=name,expectedConclusion=case['expected'],coreReport=report,assessment=assessment,
            outputHashes=hashes,cliSamples=samples,phaseRows=phase_rows,phaseOutputSha256=phase_hash,
            inspection=case.get('inspection')))
        summary=validate_measurements([rows[-1]],[name])[0]
        print(name,'CLI',round(summary['cliMedianMs'],3),'ms; phase',round(summary['phaseMedianMs'],3),'ms;',
            'PASS' if summary['met'] else 'OVER BUDGET',flush=True)
    summaries=validate_measurements(rows,[c['name'] for c in cases])
    stable=before==sources() and tools_before==tools()
    record=dict(schema='ariadne.i5b-measurements/v1',passed=stable and all(r['met'] for r in summaries),
        sourcesStable=before==sources(),toolsStable=tools_before==tools(),sourceHashes=before,tools=tools(),
        qualificationEnvironment=active_identity(),kind='controlled-windows' if args.captures else 'fixtures',
        defaultNativeVerified=True,contractSha256=sha(ROOT/'tests/input/fixtures/i5b/performance.json'),
        cases=rows,summaries=summaries,scope='Exact declared corpus; no I4 qualification or historical-path/root-cause claim.')
    (work/'report.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Report:',work/'report.json',flush=True)
    raise SystemExit(0 if record['passed'] else 1)


if __name__=='__main__':main()
