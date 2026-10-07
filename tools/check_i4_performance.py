#!/usr/bin/env python3
"""Qualify unchanged I4 budgets after exact current-source regression gates."""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tarfile

import check_bap_core
import check_i5a
import i5b_contract
from i5a_native_contract import environment, native_manifest, sha
from investigation_budget import windows_qualification
from investigation_windows_case import load_case, case_digest, materialize
from with_mirrorrust_snapshot import active_identity

ROOT = Path(__file__).resolve().parents[1]


def require(value, reason):
    if not value:
        raise ValueError(reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regressions', type=Path, required=True,
                        help='fresh complete check_i5b report, including native/core/I5a/I4 gates')
    parser.add_argument('--profiles-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    before = check_bap_core.sources()
    qualification = active_identity()
    gates, records, artifacts = [], {}, []

    def run(name, command):
        result = subprocess.run([str(x) for x in command], cwd=ROOT, env=environment(),
                                capture_output=True, text=True, timeout=1800)
        (work/(name+'.log')).write_text(result.stdout + result.stderr)
        gates.append(dict(gate=name, command=[str(x) for x in command], exitCode=result.returncode))
        require(result.returncode == 0, name+' failed')
        print(name+': PASS', flush=True)
        return result.stdout

    passed, error, tools_before = False, None, {}
    try:
        require(qualification is not None, 'sealed dependency snapshot required')
        regression = json.loads(args.regressions.read_text())
        require(regression.get('passed') is True and regression.get('fullI5bAcceptance') is True
                and regression.get('sourcesStable') is True and regression.get('toolsStable') is True
                and regression['sourceHashes'] == i5b_contract.sources()
                and regression['qualificationEnvironment'] == qualification
                and all(g['exitCode'] == 0 for g in regression['gates']), 'incomplete/stale I5b regressions')
        require(regression['tools'] == i5b_contract.tools(), 'regression tools changed')
        core = regression['records']['native-core-stage-e-input-bap-regressions']
        require(core.get('stage2Qualified') is True and core.get('defaultNativeVerified') is True
                and core.get('sourcesStable') is True and core.get('passed') is True
                and core['sourceHashes'] == before and core['tools']['qualificationEnvironment'] == qualification
                and all(g['exitCode'] == 0 for g in core['gates']), 'incomplete/stale native qualification')
        require(core['records']['generatedReplay']['helperManifest'] == native_manifest(),
                'native replay helper differs from production helper')
        i5a = regression['records']['i5a-regression']
        require(i5a.get('sourceFixtureAcceptancePassed') is True and i5a.get('passed') is True and i5a.get('sourcesStable') is True
                and i5a['sourceHashes'] == check_i5a.sources(),
                'incomplete/stale I5a regressions')
        records['regressions'] = regression
        gates.append(dict(gate='current-source-native-I5-regressions', exitCode=0,
                          command=['source-tool-environment-check', str(args.regressions)]))
        run('build-normal-cli', ['cargo','build','--offline','--locked','--release','--bin','ariadne-minidump'])
        run('build-profiler', ['cargo','build','--offline','--locked','--release','--features','bench','--bin','i4_profile'])
        tool_names = [*regression['tools'], 'target/release/i4_profile']
        tools_before = {name: sha(ROOT/name) for name in tool_names}
        output = run('exact-investigation-workloads', ['python3','tools/measure_investigation.py'])
        reports = [Path(line[8:]) for line in output.splitlines() if line.startswith('Report: ')]
        require(len(reports) == 1, 'missing exact workload record')
        workload = json.loads(reports[0].read_text())
        from measure_investigation import sources as workload_sources
        require(workload.get('passed') is True and workload.get('sourcesStable') is True
                and workload.get('toolsStable') is True and workload['sourceHashes'] == workload_sources()
                and workload['qualificationEnvironment'] == qualification, 'workload identity/regression failed')
        for name, digest in workload['tools'].items():
            require(sha(ROOT/name) == digest, 'workload tool changed: '+name)
        case = load_case()
        windows = windows_qualification(workload, case)
        require(windows['targetMet'] is True and workload['explanationPhaseBudgetMet'] is True,
                'unchanged Windows CLI or Linux phase budget failed')
        records['workload'] = workload
        records['windows98Qualification'] = windows
        artifacts.append(reports[0].parent)
        dump = materialize(case, work/'inputs')
        phases = run('native-phase-profile', [ROOT/'target/release/i4_profile', dump,
                     ROOT/'target/ariadne-llvm-mc', case['query']['entry_va'],case['query']['seed_va'],'6'])
        (work/'native-phases.csv').write_text(phases)
        rows = list(csv.DictReader(phases.splitlines()))
        baseline = list(csv.DictReader((args.profiles_root/'baseline-phases.csv').read_text().splitlines()))
        require(len(rows) == 6 and baseline, 'missing profile/baseline rows')
        expected = baseline[0]['output_sha256']
        require(all(r['decoded'] == '98' and r['output_sha256'] == expected
                    and (r['recovery_actions'],r['dataflow_actions'],r['slice_actions']) == ('99','102','15')
                    for r in rows), 'profile changed reports or action schedule')
        records['profile'] = dict(rows=rows, baselineOutputSha256=expected,
                                 diagnosticOnly=True, acceptanceUsesExplanationCLI=True)
        require(before == check_bap_core.sources(), 'sources changed during qualification')
        require(all(sha(ROOT/name) == digest for name,digest in tools_before.items()),
                'tools changed during qualification')
        passed = True
    except Exception as failure:
        error = str(failure)
        print(error, flush=True)
    record = dict(schema='ariadne.i4-performance-qualification/v1',
                  recordedUtc=datetime.now(timezone.utc).isoformat(), passed=passed,
                  fullI4RealCaptureAcceptance=passed, sourceHashes=before,
                  sourcesStable=before == check_bap_core.sources(), tools=tools_before,
                  qualificationEnvironment=qualification, activeWindowsCaseId=load_case()['id'],
                  activeWindowsCaseDigest=case_digest(load_case()), gates=gates, records=records,
                  error=error, scope='Exact controlled 98-start Windows machine-code fault-address dependency query; '
                  'native full observations, independent replay/mutations, I5 regressions and separate Linux phase; '
                  'no executed-history, ISA-step, original Electron crash or general root-cause claim.')
    (work/'report.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Report:',work/'report.json',flush=True)
    if not passed:
        raise SystemExit(1)
    # Preserve complete nested qualification, raw timing/output evidence and the
    # diagnostic/negative baselines, with every retained member verified by hash.
    archive, entries = work/'evidence.tar.gz', {}
    with tarfile.open(archive,'w:gz') as tar:
        def add(path, name):
            entries[name] = sha(path)
            tar.add(path,arcname=name,recursive=False)
        for name in before:
            add(ROOT/name,'sources/'+name)
        for name in ['report.json','native-phases.csv', *[g['gate']+'.log' for g in gates
                     if (work/(g['gate']+'.log')).is_file()]]:
            add(work/name,'qualification/'+name)
        for name in ['report.json','evidence-manifest.json','evidence.tar.gz']:
            add(args.regressions.parent/name,'regressions/'+name)
        add(Path(qualification['manifestPath']),'dependencies/mirrorrust-snapshot.json')
        for number, directory in enumerate([args.profiles_root,*artifacts]):
            for path in sorted(directory.rglob('*')):
                if path.is_file() and (path.suffix in {'.json','.csv','.txt','.ml','.log','.dmp','.dot','.stderr','.stdout','.time'} or path.name == 'ariadne-bap-core'):
                    add(path,f'profiles-and-samples/{number}/'+str(path.relative_to(directory)))
    with tarfile.open(archive,'r:gz') as tar:
        actual = {member.name: __import__('hashlib').sha256(tar.extractfile(member).read()).hexdigest()
                  for member in tar.getmembers() if member.isfile()}
    require(actual == entries, 'archive verification failed')
    manifest = dict(schema='ariadne.i4-performance-evidence/v1',verified=True,
                    archiveSha256=sha(archive),qualificationReportSha256=sha(work/'report.json'),entries=entries)
    (work/'evidence-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Verified archive:',archive,flush=True)


if __name__ == '__main__':
    main()
