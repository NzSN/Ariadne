#!/usr/bin/env python3
"""Source-bound Stage E completion: replay, mutations, native handoffs and reports."""
from datetime import datetime, timezone
import hashlib
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def sources():
    paths=set()
    for directory in ['src','tests','reports/src','reports/tests','input/src','input/tests','input/examples','ir/src','ir/tests','native/llvm_mc','native/llvm_ir','mbt/stage-e','bap/src','investigation/src','bap/tests','native/bap']:
        paths.update(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix!='.md' and not set(p.parts)&{'target','.work','__pycache__','results'})
    for name in ['Cargo.toml','Cargo.lock','reports/Cargo.toml','reports/Cargo.lock','input/Cargo.toml','input/Cargo.lock','ir/Cargo.toml','ir/Cargo.lock','bap/Cargo.toml','bap/Cargo.lock','investigation/Cargo.toml','investigation/Cargo.lock','tools/check_stage_e.py','tools/check_minidump.py','tools/check_minidump_mutations.py','Specs/AriadneMachineState.tla','Specs/AriadneLLVMIR.tla','Specs/AriadneMachineCommon.tla','Specs/AriadneTypes.tla']:
        paths.add(ROOT/name)
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minidump-record',type=Path,help='reuse an already passing minidump record only after exact source-hash verification')
    args=parser.parse_args()
    work=Path(tempfile.mkdtemp(prefix='ariadne-stage-e-completion-'));before=sources()
    env={**os.environ,'ARIADNE_LLVM_MC':str(ROOT/'target/ariadne-llvm-mc'),'ARIADNE_LLVM_IR':str(ROOT/'target/ariadne-llvm-ir'),'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
    headers=ROOT/'tmp/llvm20-headers/root/usr/include/llvm-20'
    if 'LLVM20_INCLUDE_DIR' not in env and headers.is_dir():env['LLVM20_INCLUDE_DIR']=str(headers)
    graph=ROOT/'tmp/graphviz-headers/root'
    if 'ARIADNE_DOT' not in env and (graph/'usr/bin/dot').is_file():
        env['ARIADNE_DOT']=str(graph/'usr/bin/dot');env['GVBINDIR']=str(graph/'usr/lib/x86_64-linux-gnu/graphviz')
        env['LD_LIBRARY_PATH']=str(graph/'usr/lib/x86_64-linux-gnu')+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    if 'ARIADNE_REAL_DUMPS' not in env:
        fixtures=ROOT.parent/'chromium/src/third_party/breakpad/breakpad/src/processor/testdata'
        if fixtures.is_dir():env['ARIADNE_REAL_DUMPS']=str(fixtures)
    if not env.get('ARIADNE_DOT'):raise SystemExit('Graphviz is required; set ARIADNE_DOT (not a pass)')
    gates=[
        ('native-ir-build',['bash','native/llvm_ir/build.sh']),
        ('root-tests',['cargo','test','--offline','--locked']),
        ('root-clippy',['cargo','clippy','--offline','--locked','--all-targets','--','-D','warnings']),
        ('reports-tests',['cargo','test','--offline','--locked','--manifest-path','reports/Cargo.toml']),
        ('reports-format',['cargo','fmt','--manifest-path','reports/Cargo.toml','--','--check']),
        ('reports-clippy',['cargo','clippy','--offline','--locked','--manifest-path','reports/Cargo.toml','--all-targets','--','-D','warnings']),
        ('minidump-regression',['python3','tools/check_minidump.py']),
        ('minidump-stateflow-cli',['cargo','test','--offline','--locked','--manifest-path','input/Cargo.toml','--test','stage_e','--','--ignored']),
        ('ir-tests-native-cli',['cargo','test','--offline','--locked','--manifest-path','ir/Cargo.toml','--','--include-ignored']),
        ('ir-format',['cargo','fmt','--manifest-path','ir/Cargo.toml','--','--check']),
        ('ir-clippy',['cargo','clippy','--offline','--locked','--manifest-path','ir/Cargo.toml','--all-targets','--','-D','warnings']),
        ('generated-replay-mutations',['python3','mbt/stage-e/run.py']),
    ]
    print(f'Stage E completion artifacts: {work}',flush=True);records=[];nested=None
    for name,command in gates:
        start=time.monotonic()
        try:
            if name=='minidump-regression' and args.minidump_record:
                nested=json.loads(args.minidump_record.read_text())
                valid=nested.get('passed') and nested.get('sourcesStable') and all(sha(ROOT/path)==digest for path,digest in nested['sourceSha256'].items())
                if not valid:raise RuntimeError('retained minidump record is stale or not passing')
                code=0;output=f'Reused hash-verified minidump record: {args.minidump_record}\n'
                log=work/f'{name}.log';log.write_text(output)
                records.append({'gate':name,'command':['source-hash-check',str(args.minidump_record)],'exitCode':0,'log':str(log),'reuse':'exact source hashes match; previous successful gate retained'})
                print(f'{name}: PASS (hash-verified retained record)',flush=True)
                continue
            result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=1200)
            code=result.returncode;output=result.stdout+result.stderr
        except (subprocess.TimeoutExpired,OSError) as error:code=-1;output=str(error)
        log=work/f'{name}.log';log.write_text(output)
        records.append({'gate':name,'command':command,'exitCode':code,'seconds':round(time.monotonic()-start,3),'log':str(log)})
        if name=='minidump-regression':
            for line in output.splitlines():
                if line.startswith('Report: '):
                    path=Path(line[8:]);nested=json.loads(path.read_text()) if path.is_file() else None
        print(f'{name}: {"PASS" if code==0 else "FAIL"}',flush=True)
    stable=before==sources();all_passed=stable and all(r['exitCode']==0 for r in records)
    replay_path=ROOT/'mbt/stage-e/results/latest.json';replay=json.loads(replay_path.read_text()) if all_passed else None
    if all_passed:
        for path,digest in replay['sourceHashes'].items():
            if sha(ROOT/path)!=digest:raise SystemExit(f'stale replay source: {path}')
        helper_sha=sha(ROOT/'target/ariadne-llvm-ir')
        corpus=json.loads((ROOT/'mbt/stage-e/corpus/manifest.json').read_text())
        if corpus['generation']['nativeHelperSha256']!=helper_sha:raise SystemExit('native helper differs from corpus producer; regenerate explicitly')
    profile=subprocess.run(['python3','tools/amd64_profile.py','check','--require-milestone','register-core'],cwd=ROOT,env=env,capture_output=True,text=True)
    profile_output=profile.stdout+profile.stderr;(work/'register-core.log').write_text(profile_output)
    pending=profile.returncode==1 and '0/49 verified' in profile_output and 'Milestone register-core is pending' in profile_output
    result={
        'schema':'ariadne.stage-e-completion/v1','recordedUtc':datetime.now(timezone.utc).isoformat(),
        'passed':all_passed and (pending or profile.returncode==0),'sourcesStable':stable,'sourceHashes':before,'gates':records,
        'completionClauses':{name:all_passed for name in ['validators','generatedReplayAllObservations','mutationSensitivity','frozenRecoveryHandoff','nativeVerifiedIRHandoff','separateReportsAndCLI']},
        'replay':replay,'minidumpRegression':nested,
        'tools':{'nativeIRSha256':sha(ROOT/'target/ariadne-llvm-ir'),'nativeMCSha256':sha(ROOT/'target/ariadne-llvm-mc'),'graphvizPath':env['ARIADNE_DOT'],'graphvizSha256':sha(env['ARIADNE_DOT']),'llvmHeaders':env.get('LLVM20_INCLUDE_DIR')},
        'registerCoreAcceptance':'pending 0/49' if pending else 'passed' if profile.returncode==0 else 'unexpected failure',
        'rustRefinementProof':'open; separate Stage F obligation',
        'scope':'Stage E finite generated conformance and report/CLI acceptance, relative to supplied semantic relations and verified native IR. No universal refinement or historical execution claim.',
    }
    (work/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(f'Report: {work/"report.json"}',flush=True)
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':main()
