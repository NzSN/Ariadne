#!/usr/bin/env python3
"""Compare every Rust core observation with independent TLA traces of BAP inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def run(cmd,expected=(0,),timeout=180):
    r=subprocess.run([str(x) for x in cmd],cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    if r.returncode not in expected:raise RuntimeError(r.stdout+r.stderr)
    return r

def tla(value):
    if isinstance(value,bool):return 'TRUE' if value else 'FALSE'
    if isinstance(value,str):return json.dumps(value)
    if isinstance(value,int):return str(value)
    if isinstance(value,list):return '{'+','.join(tla(v) for v in value)+'}'
    if isinstance(value,dict):return '['+','.join(k+' |-> '+tla(v) for k,v in value.items())+']'
    raise ValueError(value)

def canonical(value):
    if isinstance(value,list):return sorted([canonical(v) for v in value],key=lambda v:json.dumps(v,sort_keys=True))
    if isinstance(value,dict):return {k:canonical(v) for k,v in value.items()}
    return value

def map_rows(value,field):
    pairs=enumerate(value,1) if isinstance(value,list) else ((int(k),v) for k,v in value.items())
    return [{'va':key,field:v} for key,v in pairs]

def sources():
    paths=set()
    for tree in ['src','bap/src','reports/src','native/bap']:
        paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.md')
    paths.update(ROOT/p for p in ['Cargo.toml','Cargo.lock','bap/Cargo.toml','bap/Cargo.lock','reports/Cargo.toml','reports/Cargo.lock','tools/check_bap_model.py','Specs/Ariadne.tla','Specs/AriadneMachineCommon.tla','Specs/AriadneTypes.tla'])
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

def main():
    before=sources()
    work=Path(tempfile.mkdtemp(prefix='ariadne-bap-model-'));records=[]
    for name in ['pipeline','alias','conditional','branch','loop','weak-store','opaque-call','indirect']:
        data=json.loads(run([ROOT/'bap/target/release/bap-model-case',name]).stdout)
        inputs=data['inputs'];directory=work/name;directory.mkdir()
        for source in ['Ariadne.tla','AriadneMachineCommon.tla','AriadneTypes.tla']:shutil.copy2(ROOT/'Specs'/source,directory/source)
        cases=inputs['instructions'];names={'may_defs':'mayDefs','must_defs':'mustDefs'}
        body='CASE '+' [] '.join('a = '+str(row['va'])+' -> '+tla({names.get(k,k):v for k,v in row.items() if k!='va'}) for row in cases)
        text='''---------------- MODULE BapModel ----------------
EXTENDS AriadneMachineCommon
VARIABLES phase,pending,visited,decoded,provenance,edges,obligations,reaching,slice
Addresses == ADDRESSES
Locations == LOCATIONS
Instructions == [a \\in Addresses |-> BODY]
Core == INSTANCE Ariadne WITH SnapshotId <- SNAPSHOT,Addresses <- Addresses,Locations <- Locations,
 EntryPoints <- ENTRIES,SliceSeeds <- SEEDS,InputKind <- "dump",Captured <- CAPTURED,
 FileBacked <- {},TrustedFallback <- {},Decodable <- DECODABLE,Insn <- Instructions
Least(xs) == CHOOSE a \\in xs : \\A b \\in xs : a <= b
Ready == {a \\in decoded : ~(Core!Incoming(a) \\subseteq reaching[a])}
Init == Core!Init
Visit == phase = "recover" /\\ pending # {} /\\ Core!Visit(Least(pending))
Propagate == phase = "dataflow" /\\ Ready # {} /\\ Core!Propagate(Least(Ready))
Next == Visit \\/ Core!FinishRecovery \\/ Propagate \\/ Core!FinishDataflow \\/ Core!ExpandSlice \\/ Core!FinishSlice
vars == <<phase,pending,visited,decoded,provenance,edges,obligations,reaching,slice>>
Spec == Init /\\ [][Next]_vars /\\ WF_vars(Next)
Safety == Core!TypeOK /\\ Core!RecoveryInvariant /\\ Core!DefinitionInvariant /\\ Core!ResultInvariant
Terminates == <> (phase = "done")
TraceComplete == phase # "done"
=============================================================================
'''
        for key,value in [('ADDRESSES',tla(inputs['addresses'])),('LOCATIONS',tla(inputs['locations'])),('BODY',body),('SNAPSHOT',tla(inputs['snapshot'])),('ENTRIES',tla(inputs['entries'])),('SEEDS',tla(inputs['seeds'])),('CAPTURED',tla(inputs['captured'])),('DECODABLE',tla(inputs['decodable']))]:text=text.replace(key,value)
        model=directory/'BapModel.tla';model.write_text(text);cfg=directory/'BapModel.cfg'
        cfg.write_text('SPECIFICATION Spec\nINVARIANT Safety\nPROPERTY Terminates\nCHECK_DEADLOCK FALSE\n')
        checked=run(['tlc','-workers','1','-noGenerateSpecTE','-config',cfg,'-metadir',directory/'states',model])
        if 'Model checking completed. No error has been found.' not in checked.stdout:raise RuntimeError('TLC did not confirm safety/termination')
        cfg.write_text('INIT Init\nNEXT Next\nINVARIANTS Safety TraceComplete\nCHECK_DEADLOCK FALSE\n')
        raw=directory/'trace.json';witness=run(['tlc','-workers','1','-noGenerateSpecTE','-config',cfg,'-metadir',directory/'witness','-dumpTrace','json',raw,model],expected=(12,))
        if 'Invariant TraceComplete is violated' not in witness.stdout:raise RuntimeError('unexpected model witness failure')
        expected=[]
        for _,state in json.loads(raw.read_text())['counterexample']['state']:
            state['provenance']=map_rows(state['provenance'],'source');state['reaching']=map_rows(state['reaching'],'definitions');expected.append(state)
        if [canonical(s) for s in expected]!=[canonical(s) for s in data['observations']]:raise RuntimeError(f'full-state model mismatch: {name}')
        (directory/'actual.json').write_text(json.dumps(data,indent=2)+'\n');records.append({'case':name,'matchedStates':len(expected),'fields':9})
        print(name,len(expected),'matched states, all nine fields',flush=True)
    result={'schema':'ariadne.bap-model-replay/v1','passed':before==sources(),'sourcesStable':before==sources(),'sourceHashes':before,'observerSha256':hashlib.sha256((ROOT/'bap/target/release/bap-model-case').read_bytes()).hexdigest(),'scope':'Rust solver conformance on BAP-produced summaries; architectural projection is separately checked','cases':records,'artifacts':str(work)}
    (work/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('Report:',work/'report.json')
    if not result['passed']:raise SystemExit('model replay sources changed during validation')


if __name__=='__main__':main()
