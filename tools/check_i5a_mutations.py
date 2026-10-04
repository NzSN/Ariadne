#!/usr/bin/env python3
"""Actual I5a implementation mutations checked by unchanged independent observers."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
from rust_layout import copy_sut,source_files
ROOT=Path(__file__).resolve().parents[1]
ZERO='src/investigation/zero_address.rs'
CORPUS='independent_context_and_arithmetic_corpus'
M=[
 ('ignore-platform',ZERO,'if context.platform != "windows-amd64" {','if false {',CORPUS),
 ('ignore-exception-rip',ZERO,'if fields.get("reg:rip") != Some(&question.site) {','if false {',CORPUS),
 ('location-as-data',ZERO,'d.reported = fields.get("parameter:1").copied();','d.reported = fields.get("exception_location").copied();',CORPUS),
 ('drop-displacement',ZERO,'let mut address = expression.constant;','let mut address = 0u64;',CORPUS),
 ('rip-applied-twice',ZERO,'let mut address = expression.constant;','let mut address = if expression.terms.is_empty() { expression.constant.wrapping_add(question.site) } else { expression.constant };',CORPUS),
 ('drop-index-scale',ZERO,'value.wrapping_mul(term.coefficient)','value.wrapping_mul(1)',CORPUS),
 ('ignore-prefix',ZERO,'if guarded_prefix(&site.bytes_hex) {','if false {',CORPUS),
 ('ignore-range',ZERO,'if end.is_none_or(|end| end > 0x0000800000000000) {','if false {',CORPUS),
 ('invalid-register-zero','src/input/fault_context.rs','decoded.and_then(|r| r.get(name))','decoded.and_then(|r| r.get(name)).or(Some(&0))',CORPUS),
 ('thread-list-substitution','src/input/fault_context.rs','let decoded = metadata.exception.as_ref().map(|e| &e.registers);','let decoded = metadata.threads.first().map(|e| &e.registers);',CORPUS),
 ('promote-unknown',ZERO,'if !decision.gaps.is_empty() {\n            ZeroAddressConclusion::Unknown','if !decision.gaps.is_empty() {\n            ZeroAddressConclusion::ConsistentWithEvidence',CORPUS),
 ('numeric-observed',ZERO,'ZeroAddressAssertion::ComputedAddress { value },\n                Classification::DerivedUnderPremises,','ZeroAddressAssertion::ComputedAddress { value },\n                Classification::Observed,',CORPUS),
 ('drop-premise',ZERO,'pinned BAP lifting and the admitted address projection are trusted; no root cause or historical path is established','unqualified result',CORPUS),
 ('ignore-query','src/investigation/validate.rs','analyzer.request() != expected','false','fault_binding_is_owned_and_rejects_metadata_or_query_substitution'),
 ('ignore-claim-limit',ZERO,'claims.truncate(limits.max_claims);','// omitted claim budget','budgets_preserve_valid_unknown_results_and_invalid_questions_stay_errors'),
 ('ignore-evidence-limit',ZERO,'data.truncate(limits.max_evidence);','// omitted evidence budget','budgets_preserve_valid_unknown_results_and_invalid_questions_stay_errors'),
]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
 paths=source_files();paths.add(ROOT/'tools/check_i5a_mutations.py')
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def main():
 before=sources();work=Path(tempfile.mkdtemp(prefix='ariadne-i5a-mutations-'));sut=work/'sut';copy_sut(sut)
 tests={str(p.relative_to(sut)):sha(p) for p in (sut/'tests').rglob('*') if p.is_file()}
 env={**os.environ,'ARIADNE_LLVM_MC':str(ROOT/'target/ariadne-llvm-mc'),'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
 checked=set();results=[];print('I5a mutation artifacts:',work,flush=True)
 for name,file,old,new,test in M:
  command=['cargo','test','--offline','--locked','--release','--manifest-path',str(sut/'Cargo.toml'),'--target-dir',str(ROOT/'target/i5a-mutations'/work.name),'--test','input_i5a',test,'--','--exact']
  if test not in checked:
   baseline=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=300);(work/(name+'-baseline.log')).write_text(baseline.stdout+baseline.stderr)
   if baseline.returncode or f'test {test} ... ok' not in baseline.stdout:raise SystemExit('unchanged baseline failed: '+test)
   checked.add(test)
  p=sut/file;original=p.read_text()
  if original.count(old)!=1:raise SystemExit(f'{name}: nonunique mutation anchor ({original.count(old)})')
  p.write_text(original.replace(old,new))
  try:result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=240)
  finally:p.write_text(original)
  output=result.stdout+result.stderr;(work/(name+'.log')).write_text(output)
  detected=result.returncode==101 and f'test {test} ... FAILED' in output and 'could not compile' not in output
  results.append(dict(mutation=name,test=test,detected=detected,exitCode=result.returncode));print(name,'detected' if detected else 'NOT DETECTED',flush=True)
  if not detected:raise SystemExit(name+': no intended mismatch')
 stable=before==sources();unchanged=all(sha(sut/p)==d for p,d in tests.items())
 report=dict(schema='ariadne.i5a-mutations/v1',passed=stable and unchanged and all(r['detected'] for r in results),sourcesStable=stable,observersUnchanged=unchanged,sourceHashes=before,observerHashes=tests,mutants=results)
 (work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 if not report['passed']:raise SystemExit(1)
if __name__=='__main__':main()
