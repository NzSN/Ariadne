#!/usr/bin/env python3
"""Reject real producer/claim/binding defects through unchanged observers."""
import hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
UNIT='producer_claims_retain_byte_origins_entry_alternatives_and_capture_references'
QUERY='same_snapshot_wrong_query_and_different_snapshot_are_rejected'
SCOPE='evidence_scope_and_address_input_tampering_are_rejected'
NATIVE='aliases_joins_calls_and_weak_memory_keep_alternatives'
ADDR='memory_address_evidence_distinguishes_payload_index_displacement_and_rip'
M=[
 ('ignore-query','investigation/src/validate.rs','analyzer.request() != expected','false','investigation','explanations',QUERY),
 ('ignore-evidence-scope','investigation/src/validate.rs','e.scope_id != self.scope_id','false','investigation','explanations',SCOPE),
 ('drop-entry-alternative','investigation/src/explain.rs','self.location_gap("entry-origin", d.site, loc, Vec::new());','// omitted entry uncertainty','investigation','explanations',UNIT),
 ('fabricate-history-class','investigation/src/explain.rs','self.claim(\n                assertion,\n                Classification::DerivedUnderPremises,','self.claim(\n                assertion,\n                Classification::Observed,','investigation','explanations',UNIT),
 ('discard-join-alternatives','investigation/src/explain.rs','.filter(|d| d.loc == loc)','.filter(|d| d.loc == loc).take(1)','input','investigation',NATIVE),
 ('suppress-call-gap','investigation/src/explain.rs','== Some("opaque-call-return")','== Some("not-a-call")','input','investigation',NATIVE),
 ('claim-precise-memory','investigation/src/explain.rs','.contains("memory:any")','.contains("impossible-memory-cell")','input','investigation',NATIVE),
 ('whole-register-group','investigation/src/explain.rs','location: loc.clone(),','location: "gpr:rax".into(),','investigation','explanations',UNIT),
 ('wrong-dump-offset','input/src/investigation.rs','file_offset: c.file_offset,','file_offset: 0,','input','investigation','both_platforms_explain_address_producer_and_preserve_dump_offsets'),
 ('invent-address-inputs','bap/src/address.rs','address_inputs: v.inputs.clone(),','address_inputs: ariadne::effects::Catalogue.locations(),','bap','native',ADDR),
 ('wrong-index-scale','bap/src/address.rs','let n = 1u64 << b.constant;','let n = (1u64 << b.constant).wrapping_add(1);','bap','native',ADDR),
]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
 paths=set()
 for tree in ['src','tests','investigation/src','investigation/tests','input/src','input/tests','reports/src','bap/src','bap/tests','native/bap']:
  paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.md')
 paths.update(ROOT/p for p in ['Cargo.toml','Cargo.lock',*[f'{crate}/{f}' for crate in ['input','reports','bap','investigation'] for f in ['Cargo.toml','Cargo.lock']],'tools/check_investigation_mutations.py'])
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def run(cmd,env):return subprocess.run([str(x) for x in cmd],cwd=ROOT,env=env,text=True,capture_output=True,timeout=180)
def main():
 before=sources();work=Path(tempfile.mkdtemp(prefix='ariadne-investigation-mutations-'));sut=work/'sut';sut.mkdir();env={**os.environ,'ARIADNE_LLVM_MC':str(ROOT/'target/ariadne-llvm-mc'),'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
 for tree in ['src','tests','input/src','input/tests','reports/src','investigation/src','investigation/tests','bap/src','bap/tests','native/bap']:shutil.copytree(ROOT/tree,sut/tree)
 for name in ['Cargo.toml','Cargo.lock',*[f'{crate}/{f}' for crate in ['input','reports','bap','investigation'] for f in ['Cargo.toml','Cargo.lock']]]:shutil.copy2(ROOT/name,sut/name)
 observers={str(p.relative_to(sut)):sha(p) for c in ['input','investigation','bap'] for p in (sut/c/'tests').rglob('*') if p.is_file()}
 records=[];baseline=set();print('Mutation artifacts:',work,flush=True)
 for name,file,old,new,crate,suite,test in M:
  command=['cargo','test','--offline','--locked','--release','--manifest-path',sut/crate/'Cargo.toml','--target-dir',work/'target','--test',suite,test,'--','--exact','--include-ignored']
  if (crate,test) not in baseline:
   good=run(command,env);(work/f'{name}-baseline.log').write_text(good.stdout+good.stderr)
   if good.returncode or f'test {test} ... ok' not in good.stdout:raise SystemExit('unchanged baseline failed: '+test)
   baseline.add((crate,test))
  p=sut/file;text=p.read_text()
  if text.count(old)!=1:raise SystemExit(f'{name}: anchor not unique ({text.count(old)})')
  changed=text.replace(old,new)
  p.write_text(changed)
  try:r=run(command,env)
  finally:p.write_text(text)
  output=r.stdout+r.stderr;(work/f'{name}.log').write_text(output)
  intended=r.returncode==101 and f'test {test} ... FAILED' in output and 'could not compile' not in output and ('assertion' in output or 'unsupported claim classification' in output or 'unbound or duplicate origin location' in output)
  records.append(dict(mutation=name,test=test,intendedMismatch=intended,exitCode=r.returncode));print(name,':','intended mismatch' if intended else 'NOT ACCEPTED',flush=True)
  if not intended:raise SystemExit(name+': no intended mismatch')
 unchanged=all(sha(sut/p)==d for p,d in observers.items());stable=before==sources();report=dict(schema='ariadne.investigation-mutations/v1',passed=unchanged and stable,sourcesStable=stable,sourceHashes=before,observersUnchanged=unchanged,observerHashes=observers,mutants=records)
 (work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
