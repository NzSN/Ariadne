#!/usr/bin/env python3
"""Isolated real-code mutation runner; --check-seams performs no builds."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
MUTANTS=[
 ('np-off-by-one','src/investigation/frame_paths.rs','result.paths.len() >= q.np - 1','result.paths.len() >= q.np','strict_np_and_equal_frame_cases_preserve_empty_list_meaning'),
 ('loop-budget-ignored','src/investigation/frame_paths.rs','>= limits.max_node_visits','> limits.max_node_visits','enumerated_paths_match_64_independent_cartesian_oracles'),
 ('forged-completeness','src/investigation/frame_paths.rs','frontier.is_empty() && !blocked && result.stop_reason.is_empty()','frontier.is_empty()','every_search_work_and_retention_boundary_stays_explicit'),
 ('lost-call-activation','src/investigation/frame_paths.rs','frame: frame - 1,','frame: frame,','strict_np_and_equal_frame_cases_preserve_empty_list_meaning'),
 ('guessed-stack-slot','src/investigation/frame_unwind.rs','let slot = registers["rsp"];','let slot = original_sp;','captured_allocations_saves_and_frame_pointer_restore_only_valid_registers'),
]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group(required=True);modes.add_argument('--check-seams',action='store_true');modes.add_argument('--remote',action='store_true')
    p.add_argument('--output-dir',type=Path);a=p.parse_args()
    for name,file,before,after,observer in MUTANTS:
        assert (ROOT/file).read_text().count(before)==1,(name,'mutation seam changed')
    if a.check_seams:print('Frame mutation seams PASS: five unique real-code edits; no campaign exercised.');return
    if a.output_dir is None:p.error('--remote requires --output-dir')
    out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=False);records=[]
    for name,file,before,after,observer in MUTANTS:
        case=out/name;source=case/'source';source.mkdir(parents=True)
        for folder in ['src','tests']:shutil.copytree(ROOT/folder,source/folder)
        for item in ['Cargo.toml','Cargo.lock']:shutil.copyfile(ROOT/item,source/item)
        manifest=source/'Cargo.toml';manifest.write_text(manifest.read_text().replace('path = "../MirrorRust"','path = '+json.dumps(str(ROOT.parent/'MirrorRust'))))
        target=source/file;target.write_text(target.read_text().replace(before,after,1))
        command=['cargo','test','--offline','--locked','-j','1','--target-dir',str(case/'build')]
        command+=['--test','input_frame_paths'] if observer.startswith('captured_') else ['--lib']
        command+=[observer,'--','--nocapture']
        with (case/'observer.log').open('w') as log:r=subprocess.run(command,cwd=source,stdout=log,stderr=subprocess.STDOUT)
        text=(case/'observer.log').read_text();rejected=r.returncode!=0 and 'test result: FAILED' in text and 'panicked at' in text
        records.append(dict(name=name,observer=observer,exit=r.returncode,compiled_behavior_rejected=rejected))
        (out/'report.json').write_text(json.dumps(dict(schema='ariadne.frame-path-mutations/v1',complete=len(records)==len(MUTANTS),passed=all(r['compiled_behavior_rejected'] for r in records),records=records),indent=2)+'\n')
        if not rejected:raise SystemExit(name+': not credited as a compiled behavioral rejection')
    print('Frame mutation PASS: five compiled real-code mutants rejected.')


if __name__=='__main__':main()
