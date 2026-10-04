#!/usr/bin/env python3
"""Replay compiler-owned core and finite-stateflow corpora against native state."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'mbt'))
from tools import FIXTURES, mirrors_tools, prepare_model, sha256, verify_corpus
from binding import check_binding


def run(command, log, env=None):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, env=env,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    log.write_text(result.stdout)
    if result.returncode:
        raise RuntimeError(f'failed {command}: {result.stdout[-3000:]}')
    return result.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper-dir',type=Path,default=ROOT/'target/bap-core-stage2')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=['good','mutant'],default='good')
    parser.add_argument('--family',choices=['core','machine-state'])
    parser.add_argument('--skip-build',action='store_true')
    args=parser.parse_args();work=args.output.resolve();work.mkdir(parents=True,exist_ok=True)
    _,compiler,mirror=mirrors_tools();verify_corpus()
    core_model=prepare_model(work)
    check_binding(compiler,core_model,work/'core-binding.log')
    sys.path.insert(0,str(ROOT/'mbt/stage-e'))
    spec=importlib.util.spec_from_file_location('stage_e_prepare', ROOT/'mbt/stage-e/prepare.py')
    stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
    stage_work=work/'stateflow';stage_work.mkdir()
    stage_model=stage.prepare_model(stage_work)/'MachineStateReplay.tla'
    manifest=json.loads((ROOT/'mbt/stage-e/corpus/manifest.json').read_text())
    for field,base in [('artifacts',ROOT/'mbt/stage-e'),('oracleSources',ROOT)]:
        for path,digest in manifest[field].items():
            if sha256(base/path)!=digest: raise RuntimeError(f'stale stage E artifact {path}')
    target=ROOT/'target/bap-core-replay'
    if not args.skip_build:
        run(['cargo','build','--offline','--locked','--no-default-features','--features','mbt,bap',
             '--bin','ariadne-mbt','--bin','ariadne-stage-e-mbt','--target-dir',target],work/'build.log')
    cases={
        'core':(target/'debug/ariadne-mbt',[],core_model,ROOT/'mbt/corpus/AriadneReplay.lock.json',
                [ROOT/'mbt/corpus'/f'{x}.itf.json' for x in FIXTURES]*2),
        'machine-state':(target/'debug/ariadne-stage-e-mbt',['machine-state'],stage_model,
                ROOT/'mbt/stage-e/corpus/MachineStateReplay.lock.json',
                [ROOT/'mbt/stage-e/corpus'/f'{x}.itf.json' for x in manifest['engines']['MachineStateReplay']]*2),
    }
    env={**os.environ,'ARIADNE_REPLAY_BACKEND':'bap','ARIADNE_BAP_CORE_DIR':str(args.helper_dir.resolve())}
    reports={}
    for family,(executable,prefix,model,lock,traces) in cases.items():
        if args.family and family!=args.family:continue
        for mode in ([args.mode,'wrong-digest'] if args.mode=='good' else ['mutant']):
            key=f'{family}-{mode}'
            output=run([executable,*prefix,mode,mirror,model,lock,*traces],work/f'{key}.log',env)
            row=json.loads(output.splitlines()[-1])
            if row['analysisBackend']!='bap' or not row['gatePassed']:raise RuntimeError(key)
            row['executableSha256']=sha256(executable);reports[key]=row
            print(f'{key}: {row["status"]}; {row["observationsDispatched"]} observations',flush=True)
    result={'schema':'ariadne.bap-core-replay/v1','passed':True,'reports':reports,
            'helperManifest':json.loads((args.helper_dir/'manifest.json').read_text()),
            'mirrorSha256':sha256(mirror),'compilerSha256':sha256(compiler),
            'coreCorpusSha256':sha256(ROOT/'mbt/corpus/manifest.json'),
            'stateflowCorpusSha256':sha256(ROOT/'mbt/stage-e/corpus/manifest.json')}
    (work/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
