#!/usr/bin/env python3
"""Compile isolated alignment-hypothesis kernel mutants on remote WSL only.

--check-seams performs no builds. Each credited mutant requires its exact
unmodified native-free unit observer to pass first, then the compiled mutated
observer to fail. Compilation, timeout, transport and zero-test failures earn
no credit. Builds use their own root target/alignment-hypothesis-mutations/
subdirectories, separate from model/replay and earlier frame-structure jobs.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess

import check_frame_structure_mutations as harness

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'src/bap/alignment_hypothesis.rs'
OBSERVER = 'tests/bap/alignment_hypothesis.rs'
PREFIX = 'bap::alignment_hypothesis::tests::'
POSITIVE = 'unknown_becomes_explicitly_assumed_and_baseline_remains_unchanged'
TAMPER = 'rehashed_hypotheses_scope_source_facts_and_final_request_are_rechecked'


@dataclass(frozen=True)
class Mutation:
    name: str
    before: str
    after: str
    observer: str
    contract: str


def mutations():
    final_compare = 'if expected!=*report || expected_final!=*final_request'
    return [
        Mutation('ignore-point-filter', 'hypothesis.rsp_residues', 'guard::TOP', POSITIVE,
                 'Unknown alignment is selected only after the point mask filters actual incoming states.'),
        Mutation('hypothesis-becomes-root', 'let mut pending=BTreeSet::new(); let mut updates=0usize;',
                 'for hypothesis in hypotheses { roots.entry(hypothesis.point.as_str()).or_insert(guard::TOP); } '
                 'let mut pending=BTreeSet::new(); let mut updates=0usize;',
                 'proved_and_empty_conditional_branches_do_not_invent_reachability',
                 'An unvisited hypothesis point never creates a root or a normal edge.'),
        Mutation('assumption-relabelled-proved', 'guard::Verdict::Aligned=>Basis::Assumed',
                 'guard::Verdict::Aligned=>Basis::Proved', POSITIVE,
                 'A newly aligned conditional fact retains Assumed basis and its original baseline verdict.'),
        Mutation('ignore-hypothesis-source-bindings', final_compare,
                 'expected.hypotheses=report.hypotheses.clone(); expected.binding_sha256=binding(&expected)?; '
                 + final_compare, TAMPER,
                 'Rehashing cannot remove exact hypothesis source, scope, activation and epoch checks.'),
        Mutation('relax-closure-epoch-boundary',
                 'baseline.input.candidate_epoch>=limits.max_closure_rounds as u64',
                 'baseline.input.candidate_epoch>limits.max_closure_rounds as u64',
                 'zero_open_and_each_closure_epoch_boundary_allow_no_assumed_edge',
                 'An exhausted closure epoch cap yields no positive selection.'),
        Mutation('skip-final-request-validation', final_compare, 'if expected!=*report', TAMPER,
                 'Trusted replay compares the exact supplied final request with the independently recomputed projection.'),
    ]


def apply(original, mutation):
    spec = harness.Mutant(mutation.name, SOURCE, mutation.before, mutation.after, PREFIX + mutation.observer)
    return harness.apply(original, spec)


def inventory():
    files = harness.inventory(ROOT)
    files[str(Path(__file__).resolve().relative_to(ROOT))] = harness.sha(Path(__file__))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-seams', action='store_true')
    mode.add_argument('--remote', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--build-root', type=Path)
    parser.add_argument('--only', action='append', default=[])
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--discard-builds', action='store_true')
    args = parser.parse_args()
    selected = [row for row in mutations() if not args.only or row.name in args.only]
    harness.require((len(args.only) == len(set(args.only)) and len(selected) == len(args.only))
                    if args.only else bool(selected), 'unknown or duplicate mutant selection')
    original = (ROOT / SOURCE).read_text()
    observer = (ROOT / OBSERVER).read_text()
    for mutation in selected:
        apply(original, mutation)
        harness.require(observer.count('fn ' + mutation.observer + '(') == 1,
                        'exact positive observer missing: ' + mutation.observer)
    if args.check_seams:
        print(f'Alignment-hypothesis mutation seams PASS: {len(selected)} real-code edits and existing observers; no campaign executed')
        return
    if args.output_dir is None:
        parser.error('--remote requires --output-dir')
    harness.require(args.timeout > 0, 'timeout must be positive')
    output = args.output_dir.resolve()
    harness.require(all(not output.is_relative_to(ROOT / directory) for directory in ('src','tests','Specs','native','tools')),
                    'output must stay outside copied source trees')
    output.mkdir(parents=True, exist_ok=False)
    build = (args.build_root or ROOT / 'target/alignment-hypothesis-mutations' / output.name).resolve()
    harness.require(build.is_relative_to((ROOT / 'target').resolve()) and not build.exists(),
                    'fresh build root under checkout target/ is required')
    build.mkdir(parents=True)
    before = inventory()
    (output / 'source-inventory.json').write_text(json.dumps(before, indent=2) + '\n')
    sibling = ROOT.parent / 'MirrorRust/Cargo.toml'
    harness.require(sibling.is_file(), 'frozen optional sibling manifest missing')
    sibling_sha = harness.sha(sibling)
    (output / 'sibling-manifest.json').write_text(json.dumps({'path':str(sibling),'sha256':sibling_sha,
         'scope':'Optional resolver manifest; mbt is not activated'}, indent=2)+'\n')
    versions = subprocess.run(['rustc','-Vv'],check=True,capture_output=True,text=True).stdout
    versions += subprocess.run(['cargo','-V'],check=True,capture_output=True,text=True).stdout
    (output / 'tool-versions.txt').write_text(versions)
    env = dict(os.environ,CARGO_BUILD_JOBS='1',CARGO_INCREMENTAL='0')
    records = []
    for mutation in selected:
        case = output / mutation.name
        source = case / 'source'
        source.mkdir(parents=True)
        for directory in ('src','tests','Specs','native'):
            shutil.copytree(ROOT / directory,source / directory,ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('Cargo.toml','Cargo.lock'):
            shutil.copyfile(ROOT / name,source / name)
        manifest = source / 'Cargo.toml'
        needle = 'path = "../MirrorRust"'
        harness.require(manifest.read_text().count(needle)==1,'optional sibling dependency seam changed')
        manifest.write_text(manifest.read_text().replace(needle,'path = '+json.dumps(str(sibling.parent)),1))
        case_build = build / mutation.name
        expected = PREFIX + mutation.observer
        command = ['cargo','test','--offline','--locked','--no-default-features','--features','bap',
                   '--message-format=json','--target-dir',str(case_build),'--lib',expected,
                   '--','--exact','--nocapture','--test-threads=1']
        control = harness.observe(command,source,env,case/'control.log',args.timeout,expected,False)
        (case/'control.json').write_text(json.dumps(control,indent=2)+'\n')
        harness.require(control['baseline_passed'],'unmodified positive observer failed; no kill credit: '+mutation.name)
        target = source / SOURCE
        target.write_text(apply(target.read_text(),mutation))
        mutated_sha = harness.sha(target)
        observed = harness.observe(command,source,env,case/'mutant.log',args.timeout,expected,True)
        record = {'name':mutation.name,'contract':mutation.contract,'source_file':SOURCE,
                  'original_source_sha256':before[SOURCE],'mutant_source_sha256':mutated_sha,
                  'control':control,'mutant':observed}
        records.append(record)
        (case/'result.json').write_text(json.dumps(record,indent=2)+'\n')
        (output/'report.json').write_text(json.dumps({
            'schema':'ariadne.alignment-hypothesis-mutations/v1',
            'expected_mutants':[row.name for row in selected],
            'complete':len(records)==len(selected),
            'passed':len(records)==len(selected) and all(row['control']['baseline_passed'] and row['mutant']['compiled_behavior_rejected'] for row in records),
            'scope':'Compiled Rust conditional-alignment kernel controls; no native/ISA/universal refinement claim',
            'records':records},indent=2)+'\n')
        harness.require(observed['compiled_behavior_rejected'],'mutant escaped or compilation/transport failed; no kill credit: '+mutation.name)
        harness.require(harness.sha(target)==mutated_sha,'mutant source changed while testing')
        harness.require(inventory()==before and harness.sha(sibling)==sibling_sha,'frozen source changed during campaign')
        print(mutation.name+': positive baseline passed; compiled behavioral mutant rejected',flush=True)
        if args.discard_builds:
            shutil.rmtree(case_build)
    (output/'source-stability.json').write_text(json.dumps({'unchanged':inventory()==before})+'\n')
    print(f'Alignment-hypothesis mutations PASS: {len(records)} compiled real-code mutants rejected')


if __name__=='__main__':
    main()
