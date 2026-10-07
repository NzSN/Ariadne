#!/usr/bin/env python3
"""Kill mechanical native algorithm mutants through unchanged generated ports."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
MUTATIONS=[
 ('seed-becomes-root','core','recovery.ml','pending=input.roots','pending=S.union input.roots input.seeds'),
 ('drop-call-edge','core','recovery.ml','add "call" ins.targets (add "summary" ins.fall E.empty)','add "summary" ins.fall E.empty'),
 ('traverse-call-edge','core','recovery.ml','if k = "call" then acc else S.add b acc','S.add b acc'),
 ('early-completion','core','recovery.ml','let next = {s with phase="dataflow"}','let next = {s with phase="done"}'),
 ('possible-write-kills','core','recovery.ml','not (S.mem loc ins.must)','not (S.mem loc ins.may)'),
 ('drop-propagation','core','recovery.ml','reaching=M.add a (D.union (M.find a s.reaching) (incoming i s a)) s.reaching','reaching=M.add a D.empty s.reaching'),
 ('drop-slice-seeds','core','recovery.ml','slice=S.inter i.seeds s.decoded','slice=S.empty'),
 ('drop-slice-expansion','core','recovery.ml','slice=S.union s.slice (predecessors i s)','slice=s.slice'),
 ('drop-state-propagation','machine-state','stateflow.ml','states=M.add a (S.union (M.find a s.states) (incoming i s a)) s.states','states=M.add a S.empty s.states'),
 ('collapse-state-ids','machine-state','stateflow.ml','states=M.add a (S.union (M.find a s.states) (incoming i s a)) s.states','states=M.add a (S.singleton (S.min_elt (S.union (M.find a s.states) (incoming i s a)))) s.states'),
 ('drop-incomplete-obligations','machine-state','stateflow.ml','let obligations=S.fold (fun a -> O.add (a,"incomplete-semantics")) (S.diff nodes complete) obligations in','let obligations=obligations in'),
 ('drop-terminal-relation','machine-state','stateflow.ml','{snapshot;nodes;initial;structural;steps;terminals;complete;obligations}','{snapshot;nodes;initial;structural;steps;terminals=Terminals.empty;complete;obligations}'),
]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,log):
 r=subprocess.run([str(x) for x in cmd],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
 log.write_text(r.stdout)
 if r.returncode:raise RuntimeError(f'{cmd}: {r.stdout[-4000:]}')
 return r.stdout

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 work=args.output.resolve();work.mkdir(parents=True,exist_ok=True)
 observers=[ROOT/'src/mbt/core/adapter.rs',ROOT/'src/mbt/stage_e/ports.rs']
 observers+=list((ROOT/'src/mbt/core/generated').rglob('*.rs'))+list((ROOT/'src/mbt/stage_e/generated').rglob('*.rs'))
 before={str(p.relative_to(ROOT)):sha(p) for p in observers}
 reports=[]
 for name,family,file,old,new in MUTATIONS:
  directory=work/name;directory.mkdir();source=directory/'source';shutil.copytree(ROOT/'native/bap-core',source,ignore=shutil.ignore_patterns('__pycache__'))
  path=source/file;original=path.read_text()
  if original.count(old)!=1:raise RuntimeError(f'{name}: mutation anchor must match once')
  changed=original.replace(old,new,1);path.write_text(changed)
  (directory/'mutation.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile=file,tofile=file)))
  helper=directory/'helper'
  run([sys.executable,ROOT/'native/bap-core/build.py','--source-dir',source,'--output',helper],directory/'build.log')
  run([sys.executable,ROOT/'tools/check_bap_core_replay.py','--helper-dir',helper,'--output',directory/'replay','--mode','mutant','--family',family,'--skip-build'],directory/'replay.log')
  record=json.loads((directory/'replay/result.json').read_text());row=record['reports'][f'{family}-mutant']
  if row['status']!='mismatch' or not row['mismatch']:raise RuntimeError(f'{name}: not a behavioral mismatch')
  reports.append({'mutation':name,'family':family,'sourceSha256':sha(path),'helperManifest':record['helperManifest'],'mismatch':row['mismatch'],'observations':row['observationsDispatched']})
  print(f'{name}: behavioral mismatch at {row["mismatch"]["action"]}',flush=True)
 if before!={str(p.relative_to(ROOT)):sha(p) for p in observers}:raise RuntimeError('observer changed during mutation campaign')
 result={'schema':'ariadne.bap-core-mutations/v1','passed':True,'mutants':reports,'observerHashes':before}
 (work/'result.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
