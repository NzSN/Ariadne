#!/usr/bin/env python3
"""Qualify compiled REP regressions with exact unchanged Rust observers.

The guard mutation runner supplies strict Cargo execution, assertion matching,
binary identities, isolated SUT copying and release-cache copying. This suite
owns its cases and report identity; importing it never changes that runner's
configuration. Compile failures, timeouts and unrelated panics receive no credit.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import check_guard_admission_mutations as machinery
from rust_layout import ROOT
from with_mirrorrust_snapshot import active_identity


OBSERVER = "tests/bap/repeated_string_projection.rs"
PREFIX = "bap::projection::repeated_string_tests::"
MUTATIONS = [
    {
        "name": "omit-zero-iteration-entry",
        "source": "src/bap/projection.rs",
        "edits": [(
            "let joined = merge_data_states(head.clone(), body_output, va)?;",
            "let joined = body_output; // mutant: discard the zero-iteration entry state",
        )],
        "tests": ["exact_forms_keep_zero_iteration_origins_and_weak_memory_effects"],
        "contract": "Possible REP writes retain initial origins and cannot become definite kills.",
    },
    {
        "name": "single-body-application",
        "source": "src/bap/projection.rs",
        "edits": [(
            "if same_data_state(&head, &joined) {",
            "if same_data_state(&head, &joined) || head.repeated_strings { // mutant: stop after one body application",
        )],
        "tests": ["fixed_point_carries_origins_through_multiple_body_iterations"],
        "contract": "Loop-carried origins propagate through all dependency fixed-point iterations.",
    },
    {
        "name": "omit-target-loop-havoc",
        "source": "src/bap/target_resolution.rs",
        "observer": "tests/bap/repeated_string_consumers.rs",
        "prefix": "bap::target_resolution::repeated_string_consumers::",
        "edits": [(
            "loop_writes(body, &mut writes);",
            "if false { loop_writes(body, &mut writes); } // mutant: retain pre-loop scalar facts",
        )],
        "tests": ["target_transfer_havocs_architectural_and_virtual_loop_writes"],
        "contract": "Target transfer cannot reuse architectural or virtual constants after possible loop writes.",
    },
    {
        "name": "permit-nested-loop",
        "source": "src/bap/admission.rs",
        "edits": [(
            "if depth != 0 || has_loop {",
            "if has_loop { // mutant: permit a nested or conditional repeated-string loop",
        )],
        "tests": ["nested_sequential_and_conditionally_entered_loops_are_refused"],
        "contract": "Exact reviewed REP forms contain one top-level loop and admit no nested loop capability.",
    },
]


def source_inventory():
    inventory = machinery.source_inventory()
    for path in (Path(__file__), ROOT / "tools/with_mirrorrust_snapshot.py"):
        inventory[str(path.relative_to(ROOT))] = machinery.sha256(path)
    return dict(sorted(inventory.items()))


def check_seams(specs):
    for spec in specs:
        observer = (ROOT / spec.get("observer", OBSERVER)).read_text()
        machinery.apply_mutation((ROOT / spec["source"]).read_text(), spec)
        for name in spec["tests"]:
            count = len(re.findall(rf"(?m)^fn {re.escape(name)}\(\)", observer))
            if count != 1:
                raise ValueError(f'{spec["name"]}: exact observer {name} occurs {count} times')
    return {
        "schema": "ariadne.repeated-string-mutation-seams/v1",
        "seamsUnique": True,
        "cargoInvoked": False,
        "mutations": [{"name": spec["name"], "source": spec["source"],
                       "tests": [spec.get("prefix", PREFIX) + name for name in spec["tests"]],
                       "contract": spec["contract"]} for spec in specs],
    }


def run(output, specs, seed, keep_builds, build_jobs, timeout):
    output.mkdir(parents=True, exist_ok=False)
    before = source_inventory()
    env = {**os.environ, "CARGO_BUILD_JOBS": str(build_jobs)}
    records = []
    report = {
        "schema": "ariadne.repeated-string-mutations/v1",
        "sourceHashes": before,
        "expectedMutations": [spec["name"] for spec in specs],
        "dependencySnapshot": active_identity(),
        "seedBuildDir": str(seed) if seed else None,
        "release": True,
        "buildsDiscardedByDefault": not keep_builds,
        "mutations": records,
        "sourcesStable": False,
        "passed": False,
    }
    failure = None
    try:
        for spec in specs:
            directory = output / spec["name"]
            directory.mkdir()
            sut = directory / "sut"
            manifest = machinery.copy_sut(sut)
            copied_sources = machinery.tree_inventory(sut)
            observers = {path: digest for path, digest in copied_sources.items()
                         if path.startswith("tests/")}
            target = sut / spec["source"]
            original = target.read_bytes()
            mutant = machinery.apply_mutation(original.decode(), spec).encode()
            record = {
                "name": spec["name"], "contract": spec["contract"], "source": spec["source"],
                "originalSha256": hashlib.sha256(original).hexdigest(),
                "mutatedSha256": hashlib.sha256(mutant).hexdigest(),
                "sutSourceHashes": copied_sources, "observerHashes": observers,
                "checks": [], "sourceRestored": False, "observersUnchanged": False,
                "sutSourcesRestored": False,
            }
            records.append(record)
            build = directory / "build"
            try:
                machinery.seed_release_cache(build, seed)
                for name in spec["tests"]:
                    test = spec.get("prefix", PREFIX) + name
                    target.write_bytes(original)
                    control = machinery.run_test(directory, manifest, build, test, env,
                                                 name + "-control", timeout)
                    check = {"test": test, "control": control, "mutant": None}
                    record["checks"].append(check)
                    if not control["passed"]:
                        raise RuntimeError(f'{spec["name"]}: exact unmodified control failed: {test}')
                    target.write_bytes(mutant)
                    try:
                        changed = machinery.run_test(directory, manifest, build, test, env,
                                                     name + "-mutant", timeout)
                    finally:
                        target.write_bytes(original)
                    check["mutant"] = changed
                    if not changed["assertionRejected"]:
                        raise RuntimeError(f'{spec["name"]}: no expected named assertion rejection: {test}')
                    if source_inventory() != before:
                        raise RuntimeError("root source inventory changed during the campaign")
            finally:
                target.write_bytes(original)
                restored = machinery.tree_inventory(sut)
                record["sourceRestored"] = machinery.sha256(target) == record["originalSha256"]
                record["observersUnchanged"] = all(restored.get(path) == digest
                                                   for path, digest in observers.items())
                record["sutSourcesRestored"] = restored == copied_sources
                record["buildDiscarded"] = not keep_builds
                if not keep_builds and build.exists():
                    shutil.rmtree(build)
                (directory / "result.json").write_text(json.dumps(record, indent=2) + "\n")
            if not all(record[key] for key in ("sourceRestored", "observersUnchanged", "sutSourcesRestored")):
                raise RuntimeError(f'{spec["name"]}: source/observer bytes were not restored')
            print(f'{spec["name"]}: {len(record["checks"])} exact assertion rejection(s)', flush=True)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        failure = str(error)
    finally:
        report["sourcesStable"] = before == source_inventory()
        report["passed"] = failure is None and report["sourcesStable"] and len(records) == len(specs)
        if failure is not None:
            report["failure"] = failure
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f'Report: {output / "report.json"}', flush=True)
    if not report["passed"]:
        raise SystemExit(failure or "root source inventory changed during the campaign")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-seams", action="store_true", help="check source and observer anchors without Cargo")
    parser.add_argument("--only", action="append", choices=[spec["name"] for spec in MUTATIONS],
                        help="run only this selector; repeat for independent selected cases")
    parser.add_argument("--output", type=Path, help="new campaign directory under this repository's target/")
    parser.add_argument("--seed-build-dir", type=Path, help="release cache independently copied into each private build")
    parser.add_argument("--keep-builds", action="store_true")
    parser.add_argument("--build-jobs", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    if args.only and len(set(args.only)) != len(args.only):
        parser.error("--only selectors cannot be repeated")
    specs = [spec for spec in MUTATIONS if args.only is None or spec["name"] in args.only]
    seams = check_seams(specs)
    if args.check_seams:
        print(json.dumps(seams, indent=2))
        return
    if args.output is None:
        parser.error("--output is required unless --check-seams is selected")
    if args.build_jobs <= 0 or args.timeout_seconds <= 0:
        parser.error("build jobs and timeout must be positive")
    output = args.output.resolve()
    target_root = (ROOT / "target").resolve()
    if output == target_root or not output.is_relative_to(target_root):
        parser.error("--output must be a new child directory under repository target/")
    seed = args.seed_build_dir.resolve() if args.seed_build_dir else None
    if seed is not None and (not seed.is_dir() or seed == output
                             or output.is_relative_to(seed) or seed.is_relative_to(output)):
        parser.error("release seed must exist separately from the campaign output")
    run(output, specs, seed, args.keep_builds, args.build_jobs, args.timeout_seconds)


if __name__ == "__main__":
    main()
