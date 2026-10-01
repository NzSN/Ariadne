#!/usr/bin/env python3
"""Mechanical mutations of the real BAP producer/adapter; observers stay unchanged."""
import hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CORPUS='projection::tests::captured_bil_matches_independent_alias_flag_address_and_memory_expectations'
UNKNOWN='projection::tests::generic_unknown_keeps_old_origins_and_is_not_an_undefined_isa_claim'
TRANSPORT='session::tests::malformed_batches_bind_every_site_and_poison_failed_sessions'
NEGATIVE='calls_special_empty_lifts_prefixes_and_snapshot_reset_remain_explicit'
DISAGREE='unix::decode_length_control_and_operand_binding_disagreements_stop_without_fallback'
MUTANTS=[
 ('omit-address-read','projection.rs','address\n                .deps()\n                .into_iter()', 'LocationSet::new()\n                .into_iter()', 'lib',CORPUS),
 ('omit-carry-read','projection.rs','let value = initial(var, va)?;','let value = if var.name == "CF" { Value::Bits(vec![Bit::constant(false)]) } else { initial(var, va)? };','lib',CORPUS),
 ('partial-frame-kills-upper','projection.rs','bits.extend_from_slice(lhs.bits()?);','bits.extend_from_slice(lhs.bits()?); for bit in &mut bits { bit.original = None; }','lib',CORPUS),
 ('memory-wide-kill','projection.rs','may_defs.insert("memory:any".into());','may_defs.insert("memory:any".into()); definite.insert("memory:any".into());','lib',CORPUS),
 ('conditional-kill','projection.rs','true, // conditional choice may preserve the destination; never infer a kill','false, // mutant infers a conditional kill','lib',CORPUS),
 ('drop-unknown','projection.rs','Bit::calculated(Catalogue.locations(), true)','Bit::calculated(Catalogue.locations(), false)','lib',UNKNOWN),
 ('empty-lift-is-noop','projection.rs','statements.is_empty() || !supported(opcode)','false || !supported(opcode)','lib',UNKNOWN),
 ('wrong-va-binding','session.rs','|| lift.va != format!("0x{va:016x}")','|| false','lib',TRANSPORT),
 ('wrong-byte-binding','session.rs','|| lift.bytes\n                        != prefix[..lift.length as usize]\n                            .iter()\n                            .map(|b| format!("{b:02x}"))\n                            .collect::<String>()','|| false','lib',TRANSPORT),
 ('wrong-consumption-agreement','prepare.rs','|| lift.length != site.evidence.length\n                || lift.bytes\n                    != site\n                        .evidence\n                        .bytes\n                        .iter()\n                        .map(|b| format!("{b:02x}"))\n                        .collect::<String>()','|| false','disagreement',DISAGREE),
 ('wrong-control-agreement','prepare.rs','if !compatible {','if false && !compatible {','disagreement',DISAGREE),
 ('missing-operand-binding-check','prepare.rs','} else if !move_binding {','} else if false && !move_binding {','disagreement',DISAGREE),
 ('partial-self-move-loses-definition','projection.rs','let changed = partial_destination.contains(&cell)','let changed = false','native','partial_self_moves_define_written_cells_and_unsupported_bil_never_falls_back'),
 ('cross-snapshot-reuse','prepare.rs','self.snapshot.as_deref().is_some_and(|id| id != snapshot)','false','native',NEGATIVE),
 ('fabricated-call-preservation','prepare.rs','site.evidence.rule = Some("bap-opaque-call-return-v1".into());','site.evidence.rule = Some("bap-opaque-call-return-v1".into()); site.instruction.may_defs.retain(|l| !l.starts_with("gpr:rbx:"));','native',NEGATIVE),
]
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def execute(cmd,env,timeout=180):return subprocess.run([str(a) for a in cmd],cwd=ROOT,env=env,text=True,capture_output=True,timeout=timeout)
def command(manifest,target,suite,test):
 return ['cargo','test','--offline','--locked','--release','--manifest-path',manifest,'--target-dir',target,*(['--lib'] if suite=='lib' else ['--test',suite]),test,'--','--exact','--include-ignored']
def sources():
 paths=set()
 for tree in ['src','tests','reports/src','bap/src','bap/tests','native/bap']:
  paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.md')
 paths.update(ROOT/p for p in ['Cargo.toml','Cargo.lock','reports/Cargo.toml','reports/Cargo.lock','bap/Cargo.toml','bap/Cargo.lock','tools/check_bap_mutations.py'])
 return {str(p.relative_to(ROOT)):digest(p) for p in sorted(paths)}
def main():
 before=sources()
 work=Path(tempfile.mkdtemp(prefix='ariadne-bap-mutations-'));sut=work/'sut';sut.mkdir()
 env={**os.environ,'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'ARIADNE_LLVM_MC':str(ROOT/'target/ariadne-llvm-mc'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
 for tree in ['src','tests','reports/src','bap/src','bap/tests','native/bap']:shutil.copytree(ROOT/tree,sut/tree)
 for name in ['Cargo.toml','Cargo.lock','reports/Cargo.toml','reports/Cargo.lock','bap/Cargo.toml','bap/Cargo.lock']:shutil.copy2(ROOT/name,sut/name)
 observers={str(p.relative_to(sut)):digest(p) for p in (sut/'bap/tests').rglob('*') if p.is_file()}
 print('Mutation artifacts:',work,flush=True);baselines=set();rows=[]
 for name,file,old,new,suite,test in MUTANTS:
  cmd=command(sut/'bap/Cargo.toml',work/'target',suite,test)
  if (suite,test) not in baselines:
   good=execute(cmd,env);(work/f'{suite}-baseline.log').write_text(good.stdout+good.stderr)
   if good.returncode or f'test {test} ... ok' not in good.stdout:raise SystemExit(f'baseline failed: {test}')
   baselines.add((suite,test))
  path=sut/'bap/src'/file;original=path.read_text()
  if original.count(old)!=1:raise SystemExit(f'{name}: mutation anchor not unique ({original.count(old)})')
  path.write_text(original.replace(old,new))
  try:r=execute(cmd,env)
  finally:path.write_text(original)
  output=r.stdout+r.stderr;(work/f'{name}.log').write_text(output)
  killed=r.returncode==101 and f'test {test} ... FAILED' in output and ('assertion' in output or ': invalid batch was accepted' in output) and 'could not compile' not in output
  rows.append(dict(mutation=name,test=test,assertionRejected=killed,exitCode=r.returncode))
  print(name,':','intended assertion mismatch' if killed else 'NOT ACCEPTED',flush=True)
  if not killed:raise SystemExit(f'{name}: no intended assertion mismatch')
 # Native binding mutation: invert the two packaged EXTRACT accessors in the real emitter.
 path=sut/'native/bap/lift.cpp';original=path.read_text();old='std::to_string(bap_exp_extract_lobit(e))+",\\\"lo\\\":"+std::to_string(bap_exp_extract_hibit(e))'
 if original.count(old)!=1:raise SystemExit('extract getter mutation anchor not unique')
 new=old.replace('lobit','GETTER_TEMP').replace('hibit','lobit').replace('GETTER_TEMP','hibit');path.write_text(original.replace(old,new))
 build=execute(['bash',sut/'native/bap/build.sh',work/'bad-extract'],env)
 (work/'extract-build.log').write_text(build.stdout+build.stderr)
 if build.returncode:raise SystemExit('native mutant failed to build; not a detected defect')
 mutant_env={**env,'ARIADNE_BAP_HELPER':str(work/'bad-extract')}
 test='aliases_zero_extension_memory_and_conditional_writes_have_independent_effect_expectations'
 r=execute(command(sut/'bap/Cargo.toml',work/'target','native',test),mutant_env);output=r.stdout+r.stderr;(work/'native-extract.log').write_text(output)
 rejected=r.returncode==101 and f'test {test} ... FAILED' in output and 'BIL extraction bounds' in output and 'could not compile' not in output
 rows.append(dict(mutation='swapped-native-extract-getters',test=test,bindingValidatorRejected=rejected,exitCode=r.returncode))
 print('swapped-native-extract-getters:', 'binding validator rejected' if rejected else 'NOT ACCEPTED',flush=True)
 unchanged=all(digest(sut/p)==d for p,d in observers.items())
 stable=before==sources()
 record=dict(schema='ariadne.bap-mutations/v1',passed=rejected and unchanged and stable,sourcesStable=stable,sourceHashes=before,observersUnchanged=unchanged,observerHashes=observers,mutants=rows)
 (work/'report.json').write_text(json.dumps(record,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 if not record['passed']:raise SystemExit(1)
if __name__=='__main__':main()
