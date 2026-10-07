#!/usr/bin/env python3
"""Complete source-bound I5b gate; fixture and controlled tiers remain separate."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import time
from i5b_contract import ROOT,environment,sha,sources,tools,validate_measurements,contract
from with_mirrorrust_snapshot import active_identity


def checked_record(path):
    record=json.loads(Path(path).read_text())
    if record.get('passed') is not True or record.get('sourcesStable') is not True:
        raise ValueError('required nested record did not pass: '+str(path))
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--captures',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--mutations-record',type=Path)
    args=parser.parse_args();work=args.output.resolve();work.mkdir(parents=True,exist_ok=False)
    before=sources();env=environment()
    graph=ROOT/'tmp/graphviz-headers/root'
    if (graph/'usr/bin/dot').is_file():
        env.update(ARIADNE_DOT=str(graph/'usr/bin/dot'),GVBINDIR=str(graph/'usr/lib/x86_64-linux-gnu/graphviz'),
            LD_LIBRARY_PATH=str(graph/'usr/lib/x86_64-linux-gnu')+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else ''))
    if active_identity() is None:raise ValueError('run qualification through the sealed dependency snapshot')
    gates=[
        ('fixtures',['python3','tests/input/fixtures/make_i5b.py','--check']),
        ('decision-model',['bash','Specs/check-zero-base-offset.sh']),
        ('format',['cargo','fmt','--all','--','--check']),
        ('root-tests',['cargo','test','--offline','--locked']),
        ('core-tests',['cargo','test','--offline','--locked','--no-default-features']),
        ('clippy',['cargo','clippy','--offline','--locked','--all-features','--all-targets','--','-D','warnings']),
        ('layout',['python3','tools/check_rust_layout.py']),
        ('qualification-negative-controls',['python3','-m','unittest','discover','-s','tools','-p','test_i5b*.py','-v']),
        ('native-corpus-cli',['cargo','test','--offline','--locked','--release','--test','input_i5b','--','--include-ignored']),
        ('i5a-regression',['python3','tools/check_i5a.py']),
        ('native-core-stage-e-input-bap-regressions',['python3','tools/check_bap_core.py','--output',str(work/'native-core')]),
    ]
    rows=[];nested={}
    print('I5b qualification artifacts:',work,flush=True)
    def gate(name,command,timeout=7200):
        start=time.monotonic()
        try:
            result=subprocess.run([str(x) for x in command],cwd=ROOT,env=env,capture_output=True,text=True,timeout=timeout)
            output=result.stdout+result.stderr;code=result.returncode
            for line in output.splitlines():
                if line.startswith('Report: '): nested[name]=checked_record(line[8:])
            if name in ['i5a-regression','native-core-stage-e-input-bap-regressions'] and code==0 and name not in nested:
                raise ValueError('required nested record missing: '+name)
        except (OSError,ValueError,subprocess.TimeoutExpired) as error:
            code=-1;output=str(error)
        (work/(name+'.log')).write_text(output)
        rows.append(dict(gate=name,command=[str(x) for x in command],exitCode=code,seconds=time.monotonic()-start))
        print(name,'PASS' if code==0 else 'FAIL',flush=True)
    for name,command in gates:gate(name,command)
    # Make the precise normal CLI and benchmark binaries current before freezing
    # their identities. Feature-specific nested builds cannot qualify other bytes.
    gate('build-i5b',['cargo','build','--offline','--locked','--release','--features','bench','--bin','i5b'])
    gate('build-normal-cli',['cargo','build','--offline','--locked','--release','--bin','ariadne-minidump'])
    tool_before=tools()
    gate('legacy-i5a-bytes',['python3','tools/compare_i5b_cli.py','--baseline',str(args.baseline)])
    gate('legacy-default-bytes',['python3','tools/compare_i5a_cli.py'])
    if args.mutations_record:
        try:
            record=checked_record(args.mutations_record)
            if record['sourceHashes']!=before or record['observersUnchanged'] is not True:
                raise ValueError('mutation source/observer identities differ')
            nested['mutations']=record
            rows.append(dict(gate='mutations',command=['source-check',str(args.mutations_record)],exitCode=0,seconds=0))
        except (OSError,ValueError) as error:
            (work/'mutations.log').write_text(str(error))
            rows.append(dict(gate='mutations',command=['source-check'],exitCode=-1,seconds=0))
    else:
        gate('mutations',['python3','tools/check_i5b_mutations.py','--output',str(work/'mutations')])
    gate('fixture-measurements',['python3','tools/measure_i5b.py','--output',str(work/'fixture-measurements')])
    gate('controlled-measurements',['python3','tools/measure_i5b.py','--output',str(work/'controlled-measurements'),
        '--captures',str(args.captures)])
    stable=before==sources();tool_stable=tool_before==tools()
    correctness=all(r['exitCode']==0 for r in rows if r['gate']!='controlled-measurements')
    fixture=nested.get('fixture-measurements')
    fixture_pass=correctness and stable and tool_stable and fixture is not None
    partial=full=False
    controlled=nested.get('controlled-measurements')
    if controlled:
        expected=[label+'-'+mode for label in ['positive','refuted','unknown'] for mode in ['partial','full']]
        summaries=validate_measurements(controlled['cases'],expected)
        partial=all(r['met'] for r in summaries if r['case'].endswith('-partial'))
        full=all(r['met'] for r in summaries if r['case'].endswith('-full'))
    record=dict(schema='ariadne.i5b-qualification/v1',recordedUtc=datetime.now(timezone.utc).isoformat(),
        sourceFixtureAcceptance=fixture_pass,controlledWindowsPartialAcceptance=fixture_pass and partial,
        controlledWindowsFullAcceptance=fixture_pass and full,fullI5bAcceptance=fixture_pass and partial and full,
        passed=fixture_pass and partial and full,sourcesStable=stable,toolsStable=tool_stable,
        sourceHashes=before,tools=tools(),qualificationEnvironment=active_identity(),gates=rows,records=nested,
        sourceFixtureCases=57,independentAuxiliaryCases=1,defaultNativeVerified=True,
        scope='Finite Windows AMD64 scalar MOV base/displacement machine-code debugging; declared captures only. No historical null provenance, root cause, universal refinement, I4 waiver or packaged release claim.')
    report=work/'report.json';report.write_text(json.dumps(record,indent=2)+'\n')
    # Archive the exact source and exercised evidence closure; every entry is
    # verified by retained bytes, digest and size after creation.
    entries={}
    archive=work/'evidence.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        files={**{'sources/'+name:ROOT/name for name in before},
               **{'qualification/'+str(p.relative_to(work)):p for p in work.rglob('*') if p.is_file() and p!=archive
                  and 'sut' not in p.relative_to(work).parts},
               **{'captures/'+str(p.relative_to(args.captures)):p for p in args.captures.rglob('*') if p.is_file()
                  and p.name in ['capture.dmp','capture.json','witness.json','ariadne_crash_demo.exe','i5b-capture-bundle.json']}}
        for name,path in sorted(files.items()):
            tar.add(path,arcname=name,recursive=False);entries[name]=dict(sha256=sha(path),bytes=path.stat().st_size)
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers()
        if len(members)!=len(entries):raise ValueError('archive closure differs')
        for member in members:
            raw=tar.extractfile(member).read();expected=entries[member.name]
            if len(raw)!=expected['bytes'] or hashlib.sha256(raw).hexdigest()!=expected['sha256']:
                raise ValueError('archive entry digest differs')
    (work/'evidence-manifest.json').write_text(json.dumps(dict(schema='ariadne.i5b-evidence/v1',
        archiveSha256=sha(archive),qualificationReportSha256=sha(report),verified=True,entries=entries),indent=2)+'\n')
    print('Report:',report,flush=True)
    raise SystemExit(0 if record['passed'] else 1)


if __name__=='__main__':main()
