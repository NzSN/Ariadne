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
PREFIX='' # Observer names are fully qualified and shared across imported modules.

def mutations():
    q='investigation::frame_question::tests::'
    m='investigation::memory_refinement::tests::'
    return [
      ('starve-priority','src/bap/work_schedule.rs','let preferred = [0, 1, 0, 2][self.turn];','let preferred = 1;', 'bap::target_resolution::tests::question_resolver_services_selected_late_dispatch_before_earlier_peers',False),
      ('omit-unknown-frontier','src/investigation/frame_question.rs','for gap in &m.gaps {','for gap in m.gaps.iter().filter(|_|false) {',q+'partial_source_stays_unknown_and_roundtrips_without_helpers',False),
      ('abstract-is-witness','src/investigation/frame_question/alternative.rs','let verdict = if witness.is_some() {','let verdict = if witness.is_some() || abstract_endpoint {',q+'source_bound_witness_refutation_abstract_unknown_and_zero_work',False),
      ('propagate-through-load','src/investigation/memory_refinement.rs','TransferExpression::Unsupported { reason } => Ok((None, Some(reason.clone()))),','TransferExpression::Unsupported { reason:_ } => Ok((Some((destination,value.clone())),None)),',m+'numerical_worklist_keeps_independent_values_across_a_load_barrier',False),
      ('merge-incompatible-bits','src/bap/target_resolution/question_semantics.rs','let known = self.known & other.known & !(self.value ^ other.value);','let known = self.known;','bap::target_resolution::question_semantics::tests::zero_work_and_unknown_memory_cannot_supply_concrete_values',False),
      ('accept-regressed-revision','src/investigation/frame_question.rs','if !old\n            .recovery()','if false && !old\n            .recovery()',q+'revisions_preserve_roots_invalidate_old_conclusions_and_reject_regression',False),
      ('bypass-capture-admission','src/investigation/frame_structure.rs','if captured != request.captured {','if false && captured != request.captured {','investigation::frame_structure::tests::captured_membership_admission_and_artifact_extents_have_independent_controls',False),
      ('wrong-callee-import','src/investigation/frame_question.rs','if analysis.request() != expected.1.request()','if false && analysis.request() != expected.1.request()',q+'completed_callee_identity_and_candidate_universe_survive_focus_and_stops',False),
      ('erase-interference','src/investigation/frame_question/dependencies.rs','kind:"external_interference".into()','kind:"erased_interference".into()',q+'completed_callee_identity_and_candidate_universe_survive_focus_and_stops',False),
      ('one-store-exclusion','src/investigation/memory_refinement.rs','c.pairs.iter().all(|p| p.relation == "disjoint")','c.pairs.iter().any(|p| p.relation == "disjoint")',m+'all_store_accesses_must_be_disjoint_before_static_exclusion',False),
      ('ignore-partial-overlap','src/investigation/memory_refinement.rs','a < y && b < z','a == b',m+'modular_ranges_match_784_independent_integer_cases',False),
      ('producer-raised-host','src/reports/frame_question.rs','if !within(&value["assessment"]["limits"],','if false && !within(&value["assessment"]["limits"],',q+'partial_source_stays_unknown_and_roundtrips_without_helpers',False),
      ('premature-after-condition','src/investigation/frame_question/alternative.rs','&& (c.point.site != task.site || c.point.moment == QuestionMoment::Before)','&& true',q+'future_after_conditions_are_not_premature_model_witnesses',False),
      ('execute-captured-normal-transfer','src/investigation/frame_question/alternative.rs','if *frame == 0 && task.site == source.chain().frames[0].pc {','if false && *frame == 0 && task.site == source.chain().frames[0].pc {',q+'captured_point_is_a_before_state_boundary',False),
      ('refute-before-loop-instance-coverage','src/investigation/frame_question/alternative.rs','closed &= covered;','closed &= true;',q+'captured_loop_observation_is_not_forced_onto_its_first_visit',False),
      ('merge-different-word-widths','src/bap/target_resolution/question_semantics.rs','if self.width != other.width {','if false && self.width != other.width {',q+'partial_word_outputs_cannot_become_exact_whole_registers',False),

    ]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def inventory():
    files={str(p.relative_to(ROOT)):sha(p) for base in ['src','tests','Specs','native'] for p in (ROOT/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'target' not in p.parts}
    files.update({p:sha(ROOT/p) for p in ['Cargo.toml','Cargo.lock','tools/check_frame_question_mutations.py']});return files

def observe(command,cwd,log):
    started=time.monotonic()
    try:
        r=subprocess.run(command,cwd=cwd,env=dict(os.environ,CARGO_BUILD_JOBS='2',CARGO_INCREMENTAL='1'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=900)
        output=r.stdout;code=r.returncode;timeout=False
    except subprocess.TimeoutExpired as e:
        output=e.stdout or '';output=output.decode(errors='replace') if isinstance(output,bytes) else output;code=None;timeout=True
    log.write_text(output)
    binaries={}
    if Path(command[0]).is_file():binaries[str(command[0])]=sha(Path(command[0]))
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
        assert any(('fn '+observer.split('::')[-1]+'(') in p.read_text() for p in (ROOT/'tests').rglob('*.rs'))
    if args.check_seams:print(f'{len(mutations())} unique compiled-mutation seams and unchanged observers found');return
    assert args.run and args.output_dir
    out=args.output_dir.resolve();assert args.resume or not out.exists();out.mkdir(parents=True,exist_ok=args.resume)
    build=ROOT/'target/frame-question-mutations'/out.name;assert args.resume or not build.exists();build.mkdir(parents=True,exist_ok=args.resume)
    source=build/'source';source.mkdir(exist_ok=args.resume)
    before_inventory=inventory()
    if args.resume:assert json.loads((out/'source-inventory.json').read_text())==before_inventory,'resume refused: source/tool inventory changed'
    else:(out/'source-inventory.json').write_text(json.dumps(before_inventory,indent=2)+'\n')
    if not args.resume:
        for base in ['src','tests','Specs','native']:shutil.copytree(ROOT/base,source/base,ignore=shutil.ignore_patterns('__pycache__','target'))
        for item in ['Cargo.toml','Cargo.lock']:shutil.copyfile(ROOT/item,source/item)
        (source/'tools').mkdir();shutil.copyfile(Path(__file__),source/'tools/check_frame_question_mutations.py')
        manifest=source/'Cargo.toml';manifest.write_text(manifest.read_text().replace('path = "../MirrorRust"','path = '+json.dumps(str(ROOT.parent/'MirrorRust'))))
    records=[]
    frozen=build/'original-observer-tests'
    if args.resume and frozen.exists():assert sha(frozen)==json.loads((out/'original-binary.json').read_text())['sha256'],'frozen original binary changed'
    for name,file,before,after,observer,ignored in mutations():
        case=out/name;case.mkdir(exist_ok=args.resume);target=source/file;original=target.read_text()
        if args.resume and (case/'result.json').is_file():
            record=json.loads((case/'result.json').read_text());stdout=(case/'mutant.log').read_text()
            observed=record['mutant'];observed['behavior_rejected']=observed['returncode']==101 and not observed['timeout'] and bool(observed['binaries']) and 'test result: FAILED' in stdout and 'panicked at' in stdout and bool(re.search(r'^    '+re.escape(PREFIX+observer)+r'$',stdout,re.MULTILINE))
            if observed['behavior_rejected'] and record['control']['passed']:
                records.append(record);(case/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(name+': retained compiled failure verified from exact failure summary',flush=True);continue
        command=['cargo','test','--offline','--locked','--no-default-features','--features','input','--message-format=json','--target-dir',str(build/'target'),'--lib',PREFIX+observer,'--','--exact','--nocapture','--test-threads=1']
        if ignored:command.append('--ignored')
        if frozen.exists():
            control_command=[str(frozen),PREFIX+observer,'--exact','--nocapture','--test-threads=1']
            if ignored:control_command.append('--ignored')
            control,stdout=observe(control_command,source,case/'control.log');control['frozen_original_binary']=True
        else:
            control,stdout=observe(command,source,case/'control.log')
            executables=[]
            for line in stdout.splitlines():
                try:value=json.loads(line)
                except json.JSONDecodeError:continue
                if value.get('reason')=='compiler-artifact' and value.get('profile',{}).get('test') and value.get('executable'):executables.append(Path(value['executable']))
            assert len(executables)==1,'original test executable not identified'
            shutil.copy2(executables[0],frozen);(out/'original-binary.json').write_text(json.dumps(dict(path=str(frozen),sha256=sha(frozen),source_inventory_sha256=sha(out/'source-inventory.json')),indent=2)+'\n')
        control['passed']=control['returncode']==0 and bool(control['binaries']) and ('test '+PREFIX+observer+' ... ok') in stdout
        assert control['passed'],(name,'baseline observer failed')
        target.write_text(original.replace(before,after,1));mutant_sha=sha(target)
        result,stdout=observe(command,source,case/'mutant.log')
        result['behavior_rejected']=result['returncode']==101 and not result['timeout'] and bool(result['binaries']) and 'test result: FAILED' in stdout and 'panicked at' in stdout and bool(re.search(r'^    '+re.escape(PREFIX+observer)+r'$',stdout,re.MULTILINE))
        target.write_text(original)
        record=dict(name=name,file=file,original_sha256=hashlib.sha256(original.encode()).hexdigest(),mutant_sha256=mutant_sha,control=control,mutant=result)
        records.append(record);(case/'result.json').write_text(json.dumps(record,indent=2)+'\n')
        report=dict(schema='ariadne.frame-question-mutations/v1',complete=len(records)==len(mutations()),passed=len(records)==len(mutations()) and all(r['control']['passed'] and r['mutant']['behavior_rejected'] for r in records),records=records)
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        assert result['behavior_rejected'],(name,'escaped or compile/transport failure; no mutation credit')
        assert inventory()==before_inventory,'source changed during campaign'
        print(name+': baseline passed; compiled mutation rejected',flush=True)
    (out/'report.json').write_text(json.dumps(dict(schema='ariadne.frame-question-mutations/v1',complete=len(records)==len(mutations()),passed=len(records)==len(mutations()) and all(r['control']['passed'] and r['mutant']['behavior_rejected'] for r in records),records=records),indent=2)+'\n')
    (out/'source-stability.json').write_text(json.dumps(dict(unchanged=inventory()==before_inventory))+'\n')
if __name__=='__main__':main()
