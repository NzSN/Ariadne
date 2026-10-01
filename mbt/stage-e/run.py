#!/usr/bin/env python3
"""Complete Stage E generated replay and mechanical engine mutation acceptance."""
import argparse
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from tools import ROOT, mirrors_tools, run, sha256, work_directory, write_json
from prepare import prepare_model


def build(manifest, target, executable, log):
    run(['cargo','build','--offline','--locked','--manifest-path',manifest,'--target-dir',target],log=log,timeout=240)
    shutil.copy2(target/'debug/ariadne-stage-e-mbt',executable)
    return executable


def replay(executable, engine, mode, mirror, model, lock, traces, log):
    command=[executable,engine,mode,mirror,model,lock,*traces]
    output=run(command,expected=(0,1),log=log,timeout=120)
    report=json.loads(output.stdout.splitlines()[-1])
    if output.returncode!=0 or not report['gatePassed']:
        raise RuntimeError(f'{engine}/{mode} acceptance failed: {report}; log: {log}')
    return {'command':[str(part) for part in command], 'executableSha256':sha256(executable), **report}


def mutant(mutation, directory, shared_target):
    sut=directory/'sut';sut.mkdir()
    shutil.copytree(ROOT/'src',sut/'src')
    for name in ['Cargo.toml','Cargo.lock']:shutil.copy2(ROOT/name,sut/name)
    # Reports must depend on this same mutated core: mixing two copies of the
    # Rust Request types would be a build error, not a detected model defect.
    reports=sut/'reports';reports.mkdir()
    shutil.copytree(ROOT/'reports/src',reports/'src')
    for name in ['Cargo.toml','Cargo.lock']:shutil.copy2(ROOT/'reports'/name,reports/name)
    source=sut/mutation['file'];original=source.read_text()
    if original.count(mutation['old'])!=1:raise RuntimeError(f'mutation no longer matches once: {mutation["name"]}')
    source.write_text(original.replace(mutation['old'],mutation['new'],1))
    evaluator=directory/'evaluator';evaluator.mkdir()
    shutil.copytree(HERE/'src',evaluator/'src');shutil.copytree(HERE/'generated',evaluator/'generated')
    for path in (HERE/'generated').rglob('*'):
        if path.is_file() and sha256(path)!=sha256(evaluator/'generated'/path.relative_to(HERE/'generated')):
            raise RuntimeError('mutation changed the generated binding')
    if sha256(HERE/'src/ports.rs')!=sha256(evaluator/'src/ports.rs'):raise RuntimeError('mutation changed the observer')
    manifest=(HERE/'Cargo.toml').read_text().replace('path = "../.."',f'path = {json.dumps(str(sut))}').replace('path = "../../reports"',f'path = {json.dumps(str(reports))}').replace('path = "../../../MirrorRust"',f'path = {json.dumps(str(ROOT.parent/"MirrorRust"))}')
    (evaluator/'Cargo.toml').write_text(manifest);shutil.copy2(HERE/'Cargo.lock',evaluator/'Cargo.lock')
    executable=build(evaluator/'Cargo.toml',shared_target,directory/'ariadne-stage-e-mbt',directory/'build.log')
    return executable,sha256(source)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mirror',type=Path,help='runtime peer; defaults to installed ModelMirrors when available')
    args=parser.parse_args()
    run([sys.executable,HERE/'prepare.py','--check'],timeout=240)
    mirrors,compiler,prepared_mirror=mirrors_tools()
    mirror=(args.mirror or Path(shutil.which('ModelMirrors') or prepared_mirror)).resolve()
    work=work_directory('stage-e-completion');model_dir=prepare_model(work)
    print(f'Stage E completion logs: {work}',flush=True)
    manifest=json.loads((HERE/'corpus/manifest.json').read_text())
    paths=[*sorted((ROOT/'src').glob('*.rs')),*sorted((HERE/'src').glob('*.rs')),*sorted((HERE/'tests').glob('*.rs')),
           *sorted((ROOT/'reports/src').glob('*.rs')),*sorted((ROOT/'reports/tests').glob('*.rs')),
           HERE/'Cargo.toml',HERE/'Cargo.lock',HERE/'run.py',HERE/'prepare.py',HERE/'cases.py',HERE/'mutations.json',HERE/'test_projection.py',ROOT/'reports/Cargo.toml',ROOT/'reports/Cargo.lock']
    source_hashes={str(path.relative_to(ROOT)):sha256(path) for path in paths}
    client=ROOT.parent/'MirrorRust'
    client_hashes={str(path.relative_to(client)):sha256(path) for path in [client/'Cargo.toml',*sorted((client/'src').glob('*.rs'))]}
    corpus_digest=sha256(HERE/'corpus/manifest.json');peer_digest=sha256(mirror)
    checks=[
        [sys.executable,HERE/'test_projection.py'],
        ['cargo','fmt','--manifest-path',HERE/'Cargo.toml','--','--check'],
        ['cargo','test','--offline','--locked','--manifest-path',HERE/'Cargo.toml'],
        ['cargo','clippy','--offline','--locked','--manifest-path',HERE/'Cargo.toml','--all-targets','--','-D','warnings'],
    ]
    for index,command in enumerate(checks):run(command,log=work/f'check-{index}.log',timeout=240)
    executable=build(HERE/'Cargo.toml',HERE/'target',work/'correct-evaluator',work/'build.log')
    rows={};traces_by_engine={};lock_by_engine={};model_by_engine={}
    for engine,name in [('machine-state','MachineStateReplay'),('llvm-ir','LLVMIRReplay')]:
        traces=[HERE/'corpus'/f'{case}.itf.json' for case in manifest['engines'][name]]*2
        traces_by_engine[engine]=traces;lock=HERE/'corpus'/f'{name}.lock.json';lock_by_engine[engine]=lock;model=model_dir/f'{name}.tla';model_by_engine[engine]=model
        for mode in ['good','wrong-digest']:
            rows[f'{engine}:{mode}']=replay(executable,engine,mode,mirror,model,lock,traces,work/f'{engine}-{mode}.log')
            print(f'{engine} {mode}: {rows[f"{engine}:{mode}"]["status"]}; {rows[f"{engine}:{mode}"]["observationsDispatched"]} observations',flush=True)
    killed=[]
    for mutation in json.loads((HERE/'mutations.json').read_text()):
        directory=work/mutation['name'];directory.mkdir()
        candidate,digest=mutant(mutation,directory,HERE/'target/mutations')
        engine=mutation['engine'];row=replay(candidate,engine,'mutant',mirror,model_by_engine[engine],lock_by_engine[engine],traces_by_engine[engine],directory/'replay.log')
        if row['mismatch']['action']!=mutation['expectedAction']:raise RuntimeError(f'unexpected first mismatch: {mutation["name"]}')
        row.update(mutation=mutation['name'],mutatedSourceSha256=digest)
        write_json(directory/'report.json',row);killed.append(row)
        print(f'{mutation["name"]}: genuine mismatch at {row["mismatch"]["action"]}',flush=True)
    if any(sha256(ROOT/path)!=digest for path,digest in source_hashes.items()) or any(sha256(client/path)!=digest for path,digest in client_hashes.items()):raise RuntimeError('source/client changed during acceptance')
    if sha256(HERE/'corpus/manifest.json')!=corpus_digest or sha256(mirror)!=peer_digest:raise RuntimeError('corpus or runtime peer changed')
    for field,base in [('artifacts',HERE),('oracleSources',ROOT)]:
        if any(sha256(base/path)!=digest for path,digest in manifest[field].items()):raise RuntimeError('oracle/binding changed during replay')
    result={
        'schema':'ariadne.stage-e-completion-replay/v1','passed':True,
        'scope':'finite generated request families and 15 mechanical engine mutants; supplied semantics and universal refinement remain separate',
        'reports':rows,'mutants':killed,'sourceHashes':source_hashes,'mirrorrustSourceHashes':client_hashes,
        'oracleSourceHashes':manifest['oracleSources'],'artifactHashes':manifest['artifacts'],'corpusManifestSha256':corpus_digest,
        'caseCounts':{name:len(cases) for name,cases in manifest['engines'].items()},
        'checks':[{'command':[str(part) for part in c],'exitCode':0} for c in checks],
        'tools':{'mirrorPath':str(mirror),'mirrorSha256':peer_digest,'mirrorVersion':run([mirror,'--version']).stdout.strip(),
                 'compilerSha256':sha256(compiler),'compilerSourceRevision':run(['git','rev-parse','HEAD'],cwd=mirrors).stdout.strip(),
                 'mirrorrustRevision':run(['git','rev-parse','HEAD'],cwd=client).stdout.strip(),'rustc':run(['rustc','--version']).stdout.strip()},'logs':str(work),
    }
    (HERE/'results').mkdir(exist_ok=True);write_json(HERE/'results/latest.json',result)
    print(f'Stage E replay/mutations passed: {HERE/"results/latest.json"}',flush=True)


if __name__=='__main__':main()
