#!/usr/bin/env python3
"""Compile real-code mutations against unchanged independent observers.

Runs in a task-owned source capsule and a mutation-only target directory.
Compile failures, timeouts and missing observers never count as rejections.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
ROOT=Path(__file__).resolve().parents[1]
FILE='src/investigation/frame_connections.rs'
PREFIX='investigation::frame_connections::tests::'
ORACLE='independent_closure_partition_condensation_and_shortest_oracle'
PROJECTION='projection_keeps_off_corridor_unknowns_context_and_admitted_links_only'
CODEC='public_bound_codec_rejects_rehashed_claims_and_host_exhaustion'

def mutations():
    return [
      ('omit-off-corridor-frontier',FILE,'for gap in &m.gaps {','for gap in m.gaps.iter().filter(|_|false) {',PROJECTION,False),
      ('absence-after-stop',FILE,'connection:RepresentedConnection::UnknownWorkStopped','connection:RepresentedConnection::AbsentInRepresentedGraph',CODEC,False),
      ('merge-sccs',FILE,'if assigned[root] {','if !groups.is_empty() || assigned[root] {',ORACLE,False),
      ('split-sccs',FILE,'groups.sort();','groups = groups.into_iter().flatten().map(|n|vec![n]).collect(); groups.sort();',ORACLE,False),
      ('omit-self-loop',FILE,'let cyclic = members.len() > 1 || members.first().is_some_and(|n| self_loops.contains(n));','let cyclic = members.len() > 1;',ORACLE,False),
      ('erase-parallel-kind',FILE,'kind: e.kind,','kind: FramePathEdgeKind::Next,',PROJECTION,False),
      ('unsupported-active-link',FILE,'if link.admitted &&','if true &&',PROJECTION,False),
      ('false-shortest-label',FILE,'shortest_in_represented_graph: i == 0,','shortest_in_represented_graph: false,',ORACLE,False),
      ('np-off-by-one',FILE,'while accepted.len() < np - 1','while accepted.len() < np',ORACLE,False),
      ('producer-raised-host','src/reports/frame_connections.rs','if !policy_within(','if false && !policy_within(',CODEC,False),
      ('strip-hypothesis',FILE,'conditional_on:source.hypothesis_ids()','conditional_on:Vec::new()','conditional_saved_source_preserves_hypotheses',True),
      ('drop-source-writer','src/reports/frame_connections.rs','let source_json = super::frame_structure::render_json(bound.source())?;','let source_json = super::frame_structure::render_json(bound.source())?.replace("state:other", "state:erased");',CODEC,False),
    ]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def inventory():
    return {str(p.relative_to(ROOT)):sha(p) for base in ['src','tests','Specs'] for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'target' not in p.parts}

def observe(command,cwd,log):
    started=time.monotonic()
    try:
        r=subprocess.run(command,cwd=cwd,env=dict(os.environ,CARGO_BUILD_JOBS='2',CARGO_INCREMENTAL='1'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=900)
        output=r.stdout;code=r.returncode;timeout=False
    except subprocess.TimeoutExpired as e:
        output=e.stdout or '';output=output.decode(errors='replace') if isinstance(output,bytes) else output;code=None;timeout=True
    log.write_text(output)
    binaries={}
    for line in output.splitlines():
        try:v=json.loads(line)
        except json.JSONDecodeError:continue
        if v.get('reason')=='compiler-artifact' and v.get('executable'):
            p=Path(v['executable']);binaries[str(p)]=sha(p)
    return dict(returncode=code,timeout=timeout,seconds=time.monotonic()-started,log_sha256=sha(log),binaries=binaries),output

def main():
    p=argparse.ArgumentParser();p.add_argument('--check-seams',action='store_true');p.add_argument('--run',action='store_true');p.add_argument('--output-dir',type=Path);p.add_argument('--resume',action='store_true');args=p.parse_args()
    for name,file,before,after,observer,ignored in mutations():
        assert (ROOT/file).read_text().count(before)==1,(name,'nonunique mutation seam')
        assert ('fn '+observer+'(') in (ROOT/'tests/investigation/frame_connections.rs').read_text()
    if args.check_seams:print('12 unique compiled-mutation seams and unchanged observers found');return
    assert args.run and args.output_dir
    out=args.output_dir.resolve();assert args.resume or not out.exists();out.mkdir(parents=True,exist_ok=args.resume)
    build=ROOT/'target/frame-connections-mutations'/out.name;assert args.resume or not build.exists();build.mkdir(parents=True,exist_ok=args.resume)
    source=build/'source';source.mkdir(exist_ok=args.resume)
    before_inventory=inventory();(out/'source-inventory.json').write_text(json.dumps(before_inventory,indent=2)+'\n')
    if not args.resume:
        for base in ['src','tests','Specs','native']:shutil.copytree(ROOT/base,source/base,ignore=shutil.ignore_patterns('__pycache__','target'))
        for item in ['Cargo.toml','Cargo.lock']:shutil.copyfile(ROOT/item,source/item)
        manifest=source/'Cargo.toml';manifest.write_text(manifest.read_text().replace('path = "../MirrorRust"','path = '+json.dumps(str(ROOT.parent/'MirrorRust'))))
    records=[]
    for name,file,before,after,observer,ignored in mutations():
        case=out/name;case.mkdir(exist_ok=args.resume);target=source/file;original=target.read_text()
        if args.resume and (case/'result.json').is_file():
            record=json.loads((case/'result.json').read_text());stdout=(case/'mutant.log').read_text()
            observed=record['mutant'];observed['behavior_rejected']=observed['returncode']==101 and not observed['timeout'] and bool(observed['binaries']) and 'test result: FAILED' in stdout and 'panicked at' in stdout and bool(re.search(r'^    '+re.escape(PREFIX+observer)+r'$',stdout,re.MULTILINE))
            if observed['behavior_rejected'] and record['control']['passed']:
                records.append(record);(case/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(name+': retained compiled failure verified from exact failure summary',flush=True);continue
        command=['cargo','test','--offline','--locked','--no-default-features','--features','input','--message-format=json','--target-dir',str(build/'target'),'--lib',PREFIX+observer,'--','--exact','--nocapture','--test-threads=1']
        if ignored:command.append('--ignored')
        control,stdout=observe(command,source,case/'control.log')
        control['passed']=control['returncode']==0 and bool(control['binaries']) and ('test '+PREFIX+observer+' ... ok') in stdout
        assert control['passed'],(name,'baseline observer failed')
        target.write_text(original.replace(before,after,1));mutant_sha=sha(target)
        result,stdout=observe(command,source,case/'mutant.log')
        result['behavior_rejected']=result['returncode']==101 and not result['timeout'] and bool(result['binaries']) and 'test result: FAILED' in stdout and 'panicked at' in stdout and bool(re.search(r'^    '+re.escape(PREFIX+observer)+r'$',stdout,re.MULTILINE))
        target.write_text(original)
        record=dict(name=name,file=file,original_sha256=hashlib.sha256(original.encode()).hexdigest(),mutant_sha256=mutant_sha,control=control,mutant=result)
        records.append(record);(case/'result.json').write_text(json.dumps(record,indent=2)+'\n')
        report=dict(schema='ariadne.frame-connections-mutations/v1',complete=len(records)==12,passed=len(records)==12 and all(r['control']['passed'] and r['mutant']['behavior_rejected'] for r in records),records=records)
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        assert result['behavior_rejected'],(name,'escaped or compile/transport failure; no mutation credit')
        assert inventory()==before_inventory,'source changed during campaign'
        print(name+': baseline passed; compiled mutation rejected',flush=True)
    (out/'report.json').write_text(json.dumps(dict(schema='ariadne.frame-connections-mutations/v1',complete=len(records)==12,passed=len(records)==12 and all(r['control']['passed'] and r['mutant']['behavior_rejected'] for r in records),records=records),indent=2)+'\n')
    (out/'source-stability.json').write_text(json.dumps(dict(unchanged=inventory()==before_inventory))+'\n')
if __name__=='__main__':main()
